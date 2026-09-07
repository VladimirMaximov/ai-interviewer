import { useRef, useState } from "react";

export const RECORDING_CHUNK_MS = 10_000;

export type RecordingChunk = {
  blob: Blob;
  sequence: number;
  startOffsetMs: number;
  endOffsetMs: number;
};

export function recordingMimeType(): string {
  const candidates = ["video/webm;codecs=vp8,opus", "video/webm", "video/mp4;codecs=avc1,mp4a.40.2", "video/mp4"];
  return candidates.find((value) => MediaRecorder.isTypeSupported(value)) || "video/webm";
}

export function useContinuousRecorder(stream: MediaStream | null) {
  const recorder = useRef<MediaRecorder | null>(null);
  const startedAt = useRef(0);
  const lastChunkOffset = useRef(0);
  const sequence = useRef(0);
  const uploadQueue = useRef(Promise.resolve());
  const checksums = useRef(new Map<number, string>());
  const failedChunks = useRef(new Map<number, RecordingChunk>());
  const upload = useRef<((chunk: RecordingChunk) => Promise<string>) | null>(null);
  const [recording, setRecording] = useState(false);
  const [uploadedChunks, setUploadedChunks] = useState(0);
  const [bufferedBytes, setBufferedBytes] = useState(0);
  const [peakBufferedBytes, setPeakBufferedBytes] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const mimeType = recordingMimeType();

  const offset = () => recording ? Math.max(0, Math.round(performance.now() - startedAt.current)) : 0;

  const start = (uploadChunk: (chunk: RecordingChunk) => Promise<string>) => {
    if (!stream) throw new Error("Камера и микрофон ещё не готовы.");
    if (recorder.current) return;
    const value = new MediaRecorder(stream, { mimeType });
    startedAt.current = performance.now();
    lastChunkOffset.current = 0;
    sequence.current = 0;
    checksums.current.clear();
    failedChunks.current.clear();
    upload.current = uploadChunk;
    setUploadError(null);
    uploadQueue.current = Promise.resolve();
    value.ondataavailable = (event) => {
      if (!event.data.size) return;
      const endOffsetMs = Math.max(lastChunkOffset.current + 1, Math.round(performance.now() - startedAt.current));
      const chunk: RecordingChunk = { blob: event.data, sequence: sequence.current++, startOffsetMs: lastChunkOffset.current, endOffsetMs };
      lastChunkOffset.current = endOffsetMs;
      setBufferedBytes((current) => {
        const next = current + chunk.blob.size;
        setPeakBufferedBytes((peak) => Math.max(peak, next));
        return next;
      });
      uploadQueue.current = uploadQueue.current.catch(() => undefined).then(async () => {
        try {
          const checksum = await uploadChunk(chunk);
          checksums.current.set(chunk.sequence, checksum);
          failedChunks.current.delete(chunk.sequence);
          setUploadedChunks((count) => count + 1);
          setBufferedBytes((current) => Math.max(0, current - chunk.blob.size));
          if (!failedChunks.current.size) setUploadError(null);
        } catch {
          failedChunks.current.set(chunk.sequence, chunk);
          setUploadError("Часть видео ожидает повторной загрузки. Запись продолжается.");
        }
      });
    };
    value.start(RECORDING_CHUNK_MS);
    recorder.current = value;
    setRecording(true);
  };

  const finish = () => new Promise<string>((resolve, reject) => {
    const value = recorder.current;
    if (!value) return reject(new Error("Запись не начата."));
    value.onstop = () => {
      recorder.current = null;
      setRecording(false);
      uploadQueue.current.then(async () => {
        if (!upload.current) throw new Error("Загрузчик записи недоступен.");
        for (const chunk of [...failedChunks.current.values()].sort((left, right) => left.sequence - right.sequence)) {
          const checksum = await upload.current(chunk);
          checksums.current.set(chunk.sequence, checksum);
          failedChunks.current.delete(chunk.sequence);
          setUploadedChunks((count) => count + 1);
          setBufferedBytes((current) => Math.max(0, current - chunk.blob.size));
        }
        if (checksums.current.size !== sequence.current) throw new Error("Не все фрагменты записи загружены.");
        setUploadError(null);
        const manifest = Array.from({ length: sequence.current }, (_, index) => checksums.current.get(index) ?? "").join("");
        const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(manifest));
        resolve([...new Uint8Array(digest)].map((item) => item.toString(16).padStart(2, "0")).join(""));
      }).catch(reject);
    };
    value.stop();
  });

  const flush = async (): Promise<void> => {
    const value = recorder.current;
    if (!value || value.state !== "recording") return;
    value.requestData();
    await new Promise((resolve) => window.setTimeout(resolve, 50));
    await uploadQueue.current;
  };

  return { recording, start, flush, finish, offset, mimeType, uploadedChunks, bufferedBytes, peakBufferedBytes, uploadError };
}
