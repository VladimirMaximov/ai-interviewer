import { useEffect, useRef, useState } from "react";

export type RecorderState = "idle" | "recording" | "recorded" | "error";

type AudioRecorderProps = {
  onRecorded: (audio: Blob) => void;
  onCleared: () => void;
  onSubmit?: (audio: Blob) => Promise<void>;
};

/** Browser microphone capture with an explicit replace-before-upload action. */
export function AudioRecorder({ onRecorded, onCleared, onSubmit }: AudioRecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");
  const [message, setMessage] = useState("Запишите ответ на вопрос.");
  const [uploading, setUploading] = useState(false);
  const audioRef = useRef<Blob | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const releaseMicrophone = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
  };

  useEffect(() => releaseMicrophone, []);

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setState("error");
      setMessage("Этот браузер не поддерживает запись с микрофона.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      streamRef.current = stream;
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        const audio = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
        releaseMicrophone();
        if (audio.size === 0) {
          setState("error");
          setMessage("Запись пуста. Попробуйте ещё раз.");
          return;
        }
        onRecorded(audio);
        audioRef.current = audio;
        setState("recorded");
        setMessage("Ответ записан. Его можно заменить до отправки.");
      };
      recorder.start();
      setState("recording");
      setMessage("Идёт запись. Говорите в микрофон.");
    } catch {
      releaseMicrophone();
      setState("error");
      setMessage("Не удалось получить доступ к микрофону. Проверьте разрешение браузера.");
    }
  };

  const stopRecording = () => recorderRef.current?.state === "recording" && recorderRef.current.stop();

  const replaceRecording = () => {
    audioRef.current = null;
    onCleared();
    setState("idle");
    setMessage("Предыдущий ответ будет заменён новой записью.");
  };

  const submit = async () => {
    if (!audioRef.current || !onSubmit) return;
    setUploading(true); setMessage("Отправляем ответ и запускаем распознавание…");
    try { await onSubmit(audioRef.current); setMessage("Ответ отправлен. Текст появится после обработки."); }
    catch { setState("error"); setMessage("Не удалось отправить ответ. Попробуйте ещё раз."); }
    finally { setUploading(false); }
  };

  return (
    <section aria-labelledby="recording-title">
      <h2 id="recording-title">Аудиоответ</h2>
      <p role={state === "error" ? "alert" : "status"}>{message}</p>
      {state !== "recording" && state !== "recorded" && <button onClick={startRecording}>Начать запись</button>}
      {state === "recording" && <button onClick={stopRecording}>Остановить запись</button>}
      {state === "recorded" && <button onClick={replaceRecording}>Записать заново</button>}
      {state === "recorded" && onSubmit && <button disabled={uploading} onClick={submit}>Отправить ответ</button>}
    </section>
  );
}
