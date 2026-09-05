import { useEffect, useRef, useState } from "react";
import { CandidateQuestion } from "../../api/candidate";
import { CandidateApi } from "../../api/candidate";

type ConsentScreenProps = { onAccept: (stream: MediaStream) => Promise<void>; questions: CandidateQuestion[] };

export function ConsentScreen({ onAccept, questions }: ConsentScreenProps) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [status, setStatus] = useState("Проверяем камеру и микрофон…");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let active = true;
    void navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: true })
      .then((value) => {
        // React Strict Mode mounts effects twice in development. A stream
        // obtained by the already-cleaned effect must be closed, not handed to
        // the interview, otherwise two camera captures can briefly coexist.
        if (!active) { value.getTracks().forEach((track) => track.stop()); return; }
        stream.current = value;
        if (video.current) video.current.srcObject = value;
        setReady(true);
        setStatus("Камера и микрофон готовы");
      })
      .catch(() => active && setStatus("Не удалось получить доступ к камере или микрофону. Разрешите его в браузере и обновите страницу."));
    return () => {
      active = false;
      stream.current?.getTracks().forEach((track) => track.stop());
      stream.current = null;
    };
  }, []);
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token || !questions.length) return;
    const api = new CandidateApi();
    // Warm the private XTTS cache while the candidate reads the rules. A
    // failure is harmless: InterviewPage falls back to browser speech.
    void (async () => {
      for (const question of questions) await fetch(api.questionSpeechUrl(token, question.id));
    })();
  }, [questions]);
  // Keep the granted device permission alive while the interview screen mounts.
  // The interview recorder then reuses the browser grant without presenting a
  // second permission prompt.
  const begin = async () => { if (stream.current) { const granted = stream.current; stream.current = null; await onAccept(granted); } };
  const blocks = Object.values(questions.reduce<Record<string, CandidateQuestion[]>>((all, item) => { const key = item.block_title ?? item.block_key ?? "Интервью"; (all[key] ??= []).push(item); return all; }, {}));
  return <main className="preflight"><span className="interview-header__eyebrow">NAPOLEON [IT] · ASYNC INTERVIEW</span><h1>Всё готово к началу?</h1><p>Интервью состоит из {blocks.length || 3} блоков и {questions.length || "нескольких"} вопросов.</p><ul>{blocks.map((block) => <li key={block[0].id}>{block[0].block_title ?? block[0].block_key}: {block.length} вопроса</li>)}</ul><p>{questions.some((item) => item.kind === "coding") ? "В одном из блоков может встретиться задача на кодинг." : "Задач на кодинг в этом интервью нет."} Лимит времени отображается у вопроса; при его окончании ответ сохраняется автоматически.</p><video ref={video} autoPlay muted playsInline /><p role="status">{ready ? "✓ " : ""}{status}</p><p className="preflight__note">После нажатия запись и первый вопрос начнутся автоматически.</p><button disabled={!ready || !questions.length} onClick={() => void begin()}>Начать интервью</button></main>;
}
