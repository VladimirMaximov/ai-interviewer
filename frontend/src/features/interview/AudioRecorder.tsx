import { FaceDetector, FilesetResolver } from "@mediapipe/tasks-vision";
import { useEffect, useRef, useState } from "react";

import {
  BrowserMonitoringKind,
  FaceConditionKind,
  FaceIntegrityEvent,
  FaceIntegrityTracker,
} from "./faceIntegrity";

export type RecorderState =
  | "idle"
  | "recording"
  | "recorded"
  | "submitted"
  | "error";

export type MonitoringEventDraft = {
  kind: BrowserMonitoringKind;
  started_at_ms: number;
  ended_at_ms: number;
  confidence?: number;
  client_event_id: string;
  detector_name: "mediapipe_face_detector";
  detector_version: "face_presence_v1";
  evidence?: Blob;
};

export type RecordedAnswer = {
  audio: Blob;
  monitoringEvents: MonitoringEventDraft[];
};

type AudioRecorderProps = {
  onRecorded: (answer: RecordedAnswer) => void;
  onCleared: () => void;
  onSubmit?: (answer: RecordedAnswer) => Promise<void>;
  onStateChange?: (state: RecorderState) => void;
};

type EvidenceCapture = {
  kind: FaceConditionKind;
  recorder: MediaRecorder | null;
  chunks: BlobPart[];
  stopped: Promise<void> | null;
  stopTimer: number | null;
};

const MAX_EVIDENCE_DURATION_MS = 15_000;

const WASM_URL =
  import.meta.env.VITE_MEDIAPIPE_WASM_URL ??
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.0.1/wasm";
const MODEL_URL =
  import.meta.env.VITE_FACE_DETECTOR_MODEL_URL ??
  "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite";

/** Record an answer while monitoring only observable camera-presence events. */
export function AudioRecorder({
  onRecorded,
  onCleared,
  onSubmit,
  onStateChange,
}: AudioRecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");
  const [message, setMessage] = useState("Запишите ответ на вопрос.");
  const [monitorMessage, setMonitorMessage] = useState(
    "Камера включится только во время записи ответа.",
  );
  const [uploading, setUploading] = useState(false);
  const answerRef = useRef<RecordedAnswer | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const detectorRef = useRef<FaceDetector | null>(null);
  const trackerRef = useRef(new FaceIntegrityTracker());
  const recordingStartedAtRef = useRef<number | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const lastDetectionAtRef = useRef(0);
  const evidenceCaptureRef = useRef<EvidenceCapture | null>(null);
  const evidenceTasksRef = useRef<Promise<MonitoringEventDraft>[]>([]);
  const faceMonitoringAvailableRef = useRef(false);
  const detectionsPerformedRef = useRef(0);

  const stopDetectionLoop = () => {
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  };

  const releaseMedia = () => {
    stopDetectionLoop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  };

  useEffect(
    () => () => {
      releaseMedia();
      detectorRef.current?.close();
      detectorRef.current = null;
    },
    [],
  );

  useEffect(() => onStateChange?.(state), [onStateChange, state]);

  const elapsedMs = () =>
    recordingStartedAtRef.current === null
      ? 0
      : performance.now() - recordingStartedAtRef.current;

  const startEvidenceCapture = (kind: FaceConditionKind) => {
    const videoTracks = streamRef.current?.getVideoTracks() ?? [];
    if (!window.MediaRecorder || videoTracks.length === 0) {
      evidenceCaptureRef.current = {
        kind,
        recorder: null,
        chunks: [],
        stopped: null,
        stopTimer: null,
      };
      return;
    }
    const evidenceStream = new MediaStream(videoTracks);
    const mimeType = MediaRecorder.isTypeSupported("video/webm")
      ? "video/webm"
      : MediaRecorder.isTypeSupported("video/mp4")
        ? "video/mp4"
        : "";
    try {
      const recorder = new MediaRecorder(
        evidenceStream,
        mimeType ? { mimeType, videoBitsPerSecond: 500_000 } : undefined,
      );
      let markStopped: () => void = () => undefined;
      const stopped = new Promise<void>((resolve) => {
        markStopped = resolve;
      });
      const capture: EvidenceCapture = {
        kind,
        recorder,
        chunks: [],
        stopped,
        stopTimer: null,
      };
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) capture.chunks.push(event.data);
      };
      recorder.onstop = markStopped;
      recorder.start(1_000);
      capture.stopTimer = window.setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, MAX_EVIDENCE_DURATION_MS);
      evidenceCaptureRef.current = capture;
    } catch {
      evidenceCaptureRef.current = {
        kind,
        recorder: null,
        chunks: [],
        stopped: null,
        stopTimer: null,
      };
    }
  };

  const finishEvidenceCapture = (event: FaceIntegrityEvent) => {
    const capture = evidenceCaptureRef.current;
    evidenceCaptureRef.current = null;
    const baseEvent = {
      ...event,
      client_event_id: crypto.randomUUID(),
      detector_name: "mediapipe_face_detector" as const,
      detector_version: "face_presence_v1" as const,
    };
    if (!capture?.recorder || !capture.stopped) {
      evidenceTasksRef.current.push(Promise.resolve(baseEvent));
      return;
    }
    if (capture.stopTimer !== null) window.clearTimeout(capture.stopTimer);
    if (capture.recorder.state === "recording") capture.recorder.stop();
    evidenceTasksRef.current.push(
      capture.stopped.then(() => {
          const type = capture.recorder!.mimeType.split(";")[0];
          const evidence = new Blob(capture.chunks, {
            type: type || "video/webm",
          });
          return evidence.size > 0 ? { ...baseEvent, evidence } : baseEvent;
      }),
    );
  };

  const applyTrackerChange = (faceCount: number, atMs: number) => {
    const change = trackerRef.current.observe(faceCount, atMs);
    change.closed.forEach(finishEvidenceCapture);
    if (change.started) startEvidenceCapture(change.started);
    if (faceCount === 1) setMonitorMessage("В кадре один человек.");
    else if (faceCount === 0) setMonitorMessage("Лицо временно не найдено.");
    else setMonitorMessage("В кадре обнаружено несколько лиц.");
  };

  const beginDetectionLoop = () => {
    const scan = () => {
      const video = videoRef.current;
      const detector = detectorRef.current;
      const now = performance.now();
      if (recorderRef.current?.state !== "recording") return;
      if (
        video &&
        detector &&
        video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA &&
        now - lastDetectionAtRef.current >= 350
      ) {
        lastDetectionAtRef.current = now;
        try {
          const result = detector.detectForVideo(video, now);
          detectionsPerformedRef.current += 1;
          applyTrackerChange(result.detections.length, elapsedMs());
        } catch {
          faceMonitoringAvailableRef.current = false;
          setMonitorMessage(
            "Детектор лица перестал отвечать; это будет отмечено в ответе.",
          );
          return;
        }
      }
      animationFrameRef.current = requestAnimationFrame(scan);
    };
    animationFrameRef.current = requestAnimationFrame(scan);
  };

  const loadFaceDetector = async () => {
    if (detectorRef.current) return detectorRef.current;
    const fileset = await FilesetResolver.forVisionTasks(WASM_URL);
    detectorRef.current = await FaceDetector.createFromOptions(fileset, {
      baseOptions: { modelAssetPath: MODEL_URL },
      runningMode: "VIDEO",
      minDetectionConfidence: 0.6,
      minSuppressionThreshold: 0.3,
    });
    return detectorRef.current;
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setState("error");
      setMessage("Этот браузер не поддерживает запись камеры и микрофона.");
      return;
    }

    try {
      setMessage("Подготавливаем камеру и локальный детектор лица…");
      const detectorPromise = loadFaceDetector().catch(() => null);
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: {
          width: { ideal: 640 },
          height: { ideal: 360 },
          facingMode: "user",
        },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      const detector = await detectorPromise;

      const audioStream = new MediaStream(stream.getAudioTracks());
      const recorder = new MediaRecorder(audioStream);
      const chunks: BlobPart[] = [];
      recorderRef.current = recorder;
      trackerRef.current.reset();
      evidenceTasksRef.current = [];
      faceMonitoringAvailableRef.current = detector !== null;
      detectionsPerformedRef.current = 0;
      recordingStartedAtRef.current = performance.now();

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = async () => {
        stopDetectionLoop();
        trackerRef.current.finish(elapsedMs()).forEach(finishEvidenceCapture);
        if (
          !faceMonitoringAvailableRef.current ||
          detectionsPerformedRef.current === 0
        ) {
          evidenceTasksRef.current.push(
            Promise.resolve({
              kind: "face_detection_unavailable",
              started_at_ms: 0,
              ended_at_ms: Math.max(1, Math.round(elapsedMs())),
              client_event_id: crypto.randomUUID(),
              detector_name: "mediapipe_face_detector",
              detector_version: "face_presence_v1",
            }),
          );
        }
        const monitoringEvents = await Promise.all(evidenceTasksRef.current);
        const audio = new Blob(chunks, {
          type: recorder.mimeType || "audio/webm",
        });
        releaseMedia();
        recordingStartedAtRef.current = null;
        if (audio.size === 0) {
          setState("error");
          setMessage("Запись пуста. Попробуйте ещё раз.");
          return;
        }
        const answer = { audio, monitoringEvents };
        onRecorded(answer);
        answerRef.current = answer;
        setState("recorded");
        setMonitorMessage(
          monitoringEvents.length
            ? `Сохранено событий для ручной проверки: ${monitoringEvents.length}.`
            : "Событий присутствия в кадре не обнаружено.",
        );
        setMessage("Ответ записан. Его можно заменить до отправки.");
      };
      recorder.start(1_000);
      setState("recording");
      setMessage("Идёт запись. Говорите в микрофон.");
      if (detector) {
        setMonitorMessage("Детектор лица активен.");
        beginDetectionLoop();
      } else {
        faceMonitoringAvailableRef.current = false;
        setMonitorMessage(
          "Детектор лица недоступен; это будет отмечено в ответе.",
        );
      }
    } catch {
      releaseMedia();
      setState("error");
      setMessage(
        "Не удалось получить доступ к камере и микрофону. Проверьте разрешения браузера.",
      );
    }
  };

  const stopRecording = () => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  };

  const replaceRecording = () => {
    answerRef.current = null;
    onCleared();
    setState("idle");
    setMessage("Предыдущий ответ будет заменён новой записью.");
    setMonitorMessage("Камера включится только во время записи ответа.");
  };

  const submit = async () => {
    if (!answerRef.current || !onSubmit) return;
    setUploading(true);
    setMessage("Отправляем ответ и события для ручной проверки…");
    try {
      await onSubmit(answerRef.current);
      setState("submitted");
      setMessage("Ответ отправлен. Текст и сигналы обрабатываются отдельно.");
    } catch {
      setState("recorded");
      setMessage("Не удалось отправить ответ. Нажмите «Отправить» ещё раз.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <section aria-labelledby="recording-title">
      <h2 id="recording-title">Аудиоответ и контроль присутствия</h2>
      <video
        ref={videoRef}
        muted
        playsInline
        aria-label="Предпросмотр камеры кандидата"
        style={{
          display: state === "recording" ? "block" : "none",
          width: "min(100%, 640px)",
          borderRadius: "12px",
          background: "#111827",
        }}
      />
      <p role={state === "error" ? "alert" : "status"}>{message}</p>
      <p role="status">{monitorMessage}</p>
      {state !== "recording" && state !== "recorded" && (
        <button onClick={startRecording}>Начать запись</button>
      )}
      {state === "recording" && (
        <button onClick={stopRecording}>Остановить запись</button>
      )}
      {state === "recorded" && (
        <button onClick={replaceRecording}>Записать заново</button>
      )}
      {state === "recorded" && onSubmit && (
        <button disabled={uploading} onClick={submit}>
          Отправить ответ
        </button>
      )}
    </section>
  );
}
