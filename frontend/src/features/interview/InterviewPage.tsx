import { useEffect, useMemo, useState } from "react";
import { CandidateApi, RecordingGrant, Transcript } from "../../api/candidate";
import { CameraPreview } from "./CameraPreview";
import { QuestionPlayer } from "./QuestionPlayer";
import { RecordingChunk, useContinuousRecorder } from "./useContinuousRecorder";
import { useInterviewMediaStream } from "./useInterviewMediaStream";
import { InterviewerAvatar } from "./InterviewerAvatar";
import { useQuestionSpeech } from "./useQuestionSpeech";

const questions = [
  { id: "11111111-1111-4111-8111-111111111111", text: "Расскажите о последнем проекте и вашей роли в нём." },
  { id: "22222222-2222-4222-8222-222222222222", text: "Как вы обычно находите и устраняете сложную техническую проблему?" },
  { id: "33333333-3333-4333-8333-333333333333", text: "Какие технологии вы хотели бы применять в следующем проекте?" },
];

type SavedAnswer = { responseId: string; startOffsetMs: number; endOffsetMs: number; transcript: Transcript };

function debugTranscript(answer: SavedAnswer | undefined, finished: boolean): string {
  if (!answer) return "ещё не сохранён";
  if (answer.transcript.status === "pending") {
    return finished ? "ожидает запуска расшифровки" : "ожидает завершения интервью";
  }
  if (answer.transcript.status === "processing") return "расшифровывается…";
  if (answer.transcript.status === "failed") return "не удалось распознать";
  return answer.transcript.text ? `готово — ${answer.transcript.text}` : "готово, речи не найдено";
}

async function sha256(blob: Blob): Promise<string> {
  return crypto.subtle.digest("SHA-256", await blob.arrayBuffer()).then((digest) =>
    [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join(""),
  );
}

async function wait(milliseconds: number): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export function InterviewPage() {
  const token = useMemo(() => new URLSearchParams(window.location.search).get("token"), []);
  const debug = useMemo(() => new URLSearchParams(window.location.search).get("debug") === "1", []);
  const { stream, error: mediaError, stop: stopMedia } = useInterviewMediaStream(true);
  const continuous = useContinuousRecorder(stream);
  const speech = useQuestionSpeech();
  const api = useMemo(() => new CandidateApi(), []);
  const [index, setIndex] = useState(0);
  const [recordingGrant, setRecordingGrant] = useState<RecordingGrant | null>(null);
  const [answerStartedAt, setAnswerStartedAt] = useState(0);
  const [answers, setAnswers] = useState<Record<string, SavedAnswer>>({});
  const [message, setMessage] = useState("Разрешите доступ к камере и микрофону.");
  const [submitting, setSubmitting] = useState(false);
  const [finished, setFinished] = useState(false);
  const question = questions[index];
  const allSaved = questions.every(({ id }) => answers[id]);

  useEffect(() => {
    if (!continuous.recording || !token) return;
    void api.timeline(token, "question_shown", continuous.offset(), question.id);
  }, [api, continuous.recording, index, question.id, token]);

  useEffect(() => {
    if (continuous.recording) speech.speak(question.text);
  }, [continuous.recording, index, question.text, speech.speak]);

  useEffect(() => {
    if (!continuous.recording || !token) return;
    const track = (eventType: string) => { void api.timeline(token, eventType, continuous.offset(), question.id); };
    const onVisibilityChange = () => track(document.hidden ? "page_hidden" : "page_visible");
    const onBlur = () => track("window_blurred");
    const onFocus = () => track("window_focused");
    const onCopy = () => track("page_copy");
    document.addEventListener("visibilitychange", onVisibilityChange);
    document.addEventListener("copy", onCopy);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      document.removeEventListener("copy", onCopy);
      window.removeEventListener("blur", onBlur);
      window.removeEventListener("focus", onFocus);
    };
  }, [api, continuous.recording, question.id, token]);

  const start = async () => {
    if (!token) { setMessage("В ссылке отсутствует токен интервью."); return; }
    try {
      setMessage("Подготавливаем защищённую запись…");
      const grant = await api.startRecording(token, continuous.mimeType.split(";")[0]);
      const uploadChunk = async (chunk: RecordingChunk): Promise<string> => {
        const checksum = await sha256(chunk.blob);
        let lastError: unknown;
        for (let attempt = 0; attempt < 3; attempt += 1) {
          try {
            const chunkGrant = await api.recordingChunkGrant(token, grant.recording_id, chunk.sequence, chunk.startOffsetMs, chunk.endOffsetMs, grant.content_type);
            await api.upload(chunkGrant.upload_url, chunk.blob, chunkGrant.content_type);
            await api.confirmRecordingChunk(token, chunkGrant.chunk_id, checksum);
            return checksum;
          } catch (error) {
            lastError = error;
            await wait((attempt + 1) * 500);
          }
        }
        throw lastError;
      };
      continuous.start(uploadChunk);
      setRecordingGrant(grant);
      setAnswerStartedAt(0);
      await api.timeline(token, "recording_started", 0);
      speech.speak(question.text);
      setMessage("Идёт непрерывная запись 720p. Каждые 10 секунд видео отправляется в защищённое хранилище.");
    } catch {
      setMessage("Не удалось начать запись: проверьте разрешения камеры. Если интервью уже завершено, используйте новую ссылку.");
    }
  };

  const saveAndContinue = async () => {
    if (!token || !continuous.recording || submitting) return;
    const endOffsetMs = continuous.offset();
    if (endOffsetMs <= answerStartedAt) { setMessage("Запишите хотя бы несколько секунд ответа."); return; }
    setSubmitting(true);
    try {
      const segment = await api.saveSegment(token, question.id, answerStartedAt, endOffsetMs);
      await api.timeline(token, "answer_saved", endOffsetMs, question.id);
      setAnswers((current) => ({ ...current, [question.id]: { responseId: segment.response_id, startOffsetMs: answerStartedAt, endOffsetMs, transcript: { status: segment.status, text: null } } }));
      if (index < questions.length - 1) {
        await api.timeline(token, "next_question_clicked", endOffsetMs, question.id);
        setIndex((current) => current + 1);
        setAnswerStartedAt(endOffsetMs);
        setMessage("Следующий вопрос показан. Запись не прерывалась.");
      } else {
        setMessage("Все ответы сохранены. Завершите интервью, чтобы отправить единый видеофайл.");
      }
    } catch {
      setMessage("Не удалось сохранить границу ответа. Запись продолжается — попробуйте ещё раз.");
    } finally {
      setSubmitting(false);
    }
  };

  const pollTranscripts = (saved: Record<string, SavedAnswer>) => {
    if (!token || !debug) return;
    void (async () => {
      let pending: ReadonlyArray<readonly [string, SavedAnswer]> = Object.entries(saved);
      while (pending.length) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        const updated = await Promise.all(pending.map(async ([id, answer]) => [id, { ...answer, transcript: await api.transcript(token, answer.responseId) }] as const));
        setAnswers((current) => ({ ...current, ...Object.fromEntries(updated) }));
        pending = updated.filter(([, answer]) => answer.transcript.status === "pending" || answer.transcript.status === "processing");
      }
    })();
  };

  const finish = async () => {
    if (!token || !recordingGrant || submitting || !allSaved) return;
    setSubmitting(true);
    try {
      const endOffsetMs = continuous.offset();
      await api.timeline(token, "interview_submitted", endOffsetMs, question.id);
      setMessage("Догружаем последний фрагмент и завершаем интервью…");
      const manifestChecksum = await continuous.finish();
      await api.finishRecording(token, recordingGrant.recording_id, manifestChecksum);
      stopMedia();
      speech.stop();
      setFinished(true);
      setMessage("Интервью сохранено. Расшифровка выполняется в фоне.");
      pollTranscripts(answers);
    } catch {
      setMessage("Не удалось завершить интервью. Не закрывайте страницу и повторите отправку.");
    } finally {
      setSubmitting(false);
    }
  };

  return <main className="interview-shell">
    <header className="interview-header"><div><span className="interview-header__eyebrow">NAPOLEON IT · ASYNC INTERVIEW</span><h1>Техническое интервью</h1></div><span className="interview-header__recording">{continuous.recording ? "● Запись идёт" : finished ? "✓ Интервью завершено" : "Камера готова"}</span></header>
    {mediaError && <p role="alert">{mediaError}</p>}
    <section className="interview-stage">
      <CameraPreview stream={stream} />
      <div className="stage-topline"><span>ВАША КАМЕРА</span><span>Вопрос {index + 1} / {questions.length}</span></div>
      <div className="question-overlay"><InterviewerAvatar compact speaking={speech.speaking} /><QuestionPlayer index={index} total={questions.length} text={question.text} onSpeak={() => speech.speak(question.text)} speaking={speech.speaking} /></div>
    </section>
    <section className="recording-controls"><div><p role="status">{message}</p>{continuous.recording && <span className="recording-controls__status">{Math.round(continuous.offset() / 1000)} с · сохранено фрагментов: {continuous.uploadedChunks}</span>}</div>{!continuous.recording && !finished && <button disabled={!stream || submitting} onClick={() => void start()}>Начать интервью</button>}{continuous.recording && !answers[question.id] && <button disabled={submitting} onClick={() => void saveAndContinue()}>{index === questions.length - 1 ? "Сохранить ответ" : "Сохранить и продолжить"}</button>}{continuous.recording && index === questions.length - 1 && allSaved && <button disabled={submitting} onClick={() => void finish()}>Завершить интервью</button>}</section>
    {debug && <section className="debug-panel" aria-label="Отладочная расшифровка"><h2>Отладка: расшифровка</h2><p>Буфер чанков в приложении: {(continuous.bufferedBytes / 1024 / 1024).toFixed(1)} MiB; пик: {(continuous.peakBufferedBytes / 1024 / 1024).toFixed(1)} MiB.</p>{questions.map(({ id }, itemIndex) => <p key={id}>Вопрос {itemIndex + 1}: {debugTranscript(answers[id], finished)}</p>)}</section>}
  </main>;
}
