import { useEffect, useMemo, useRef, useState } from "react";
import { CandidateApi, CandidateQuestion, FollowUpQuestion, RecordingGrant, Transcript } from "../../api/candidate";
import { CameraPreview } from "./CameraPreview";
import { CodeEditor } from "./CodeEditor";
import { QuestionPlayer } from "./QuestionPlayer";
import { RecordingChunk, useContinuousRecorder } from "./useContinuousRecorder";
import { useInterviewMediaStream } from "./useInterviewMediaStream";
import { InterviewerAvatar } from "./InterviewerAvatar";
import { useQuestionSpeech } from "./useQuestionSpeech";

type SavedAnswer = { responseId: string; startOffsetMs: number; endOffsetMs: number; transcript: Transcript };
type InterviewQuestion = CandidateQuestion & { isFollowUp?: boolean };

function debugTranscript(answer: SavedAnswer | undefined, finished: boolean, question: InterviewQuestion): string {
  if (!answer) return "ещё не сохранён";
  if (question.kind === "coding") {
    if (answer.transcript.status === "pending") return "код сохранён; голос ожидает расшифровки";
    if (answer.transcript.status === "processing") return "код сохранён; голос расшифровывается…";
    if (answer.transcript.status === "failed") return "код сохранён; голос не удалось распознать";
    return answer.transcript.text
      ? `код сохранён; голос — ${answer.transcript.text}`
      : "код сохранён; речи не найдено";
  }
  if (answer.transcript.status === "pending") {
    return finished ? "ожидает запуска расшифровки" : "ожидает завершения интервью";
  }
  if (answer.transcript.status === "processing") return "расшифровывается…";
  if (answer.transcript.status === "failed") return "не удалось распознать";
  return answer.transcript.text ? `готово — ${answer.transcript.text}` : "готово, речи не найдено";
}

function formatDuration(milliseconds: number): string {
  const seconds = Math.round(milliseconds / 1000);
  return `${Math.floor(seconds / 60)} мин ${seconds % 60} с`;
}

async function sha256(blob: Blob): Promise<string> {
  return crypto.subtle.digest("SHA-256", await blob.arrayBuffer()).then((digest) =>
    [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join(""),
  );
}

async function wait(milliseconds: number): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

export function InterviewPage({ baseQuestions, initialStream = null }: { baseQuestions: CandidateQuestion[]; initialStream?: MediaStream | null }) {
  const token = useMemo(() => new URLSearchParams(window.location.search).get("token"), []);
  const debug = useMemo(() => new URLSearchParams(window.location.search).get("debug") === "1", []);
  const { stream, error: mediaError, stop: stopMedia } = useInterviewMediaStream(true, initialStream);
  const continuous = useContinuousRecorder(stream);
  const speech = useQuestionSpeech();
  const api = useMemo(() => new CandidateApi(), []);
  const [index, setIndex] = useState(0);
  const [questions, setQuestions] = useState<InterviewQuestion[]>(baseQuestions);
  const [recordingGrant, setRecordingGrant] = useState<RecordingGrant | null>(null);
  const [answerStartedAt, setAnswerStartedAt] = useState(0);
  const [answers, setAnswers] = useState<Record<string, SavedAnswer>>({});
  // The stream is normally granted on the preflight screen and handed over to
  // this component. Do not show a stale permission prompt while recording is
  // being started in the background.
  const [message, setMessage] = useState(initialStream
    ? "Подготавливаем защищённую запись и первый вопрос…"
    : "Подготавливаем камеру и микрофон…");
  const [submitting, setSubmitting] = useState(false);
  const [finished, setFinished] = useState(false);
  const [recordedDurationMs, setRecordedDurationMs] = useState<number | null>(null);
  const [code, setCode] = useState("");
  const [language, setLanguage] = useState("Python");
  const [timerOffsetMs, setTimerOffsetMs] = useState(0);
  const timedOutQuestions = useRef(new Set<string>());
  const autoStarted = useRef(false);
  const question = questions[index];
  const allSaved = questions.every(({ id }) => answers[id]);
  const blocks = baseQuestions.reduce<Record<string, CandidateQuestion[]>>((groups, item) => {
    const key = item.block_key ?? "interview";
    (groups[key] ??= []).push(item);
    return groups;
  }, {});

  useEffect(() => {
    if (!continuous.recording || !token) return;
    void api.timeline(token, "question_shown", continuous.offset(), question.id);
  }, [api, continuous.recording, index, question.id, token]);

  const speakQuestion = () => speech.speak(
    question.text,
    token ? api.questionSpeechUrl(token, question.id) : undefined,
  );

  useEffect(() => {
    if (continuous.recording) void speakQuestion();
  }, [continuous.recording, question.id]);

  const refreshFollowUps = async (): Promise<InterviewQuestion[]> => {
    if (!token) return questions;
    const followUps: FollowUpQuestion[] = await api.followUps(token);
    const updated = [...baseQuestions, ...followUps.map((item) => ({ id: item.id, text: item.text, kind: "spoken" as const, block_key: "follow_up", block_title: "Уточнения", time_limit_seconds: null, isFollowUp: true }))];
    setQuestions(updated);
    return updated;
  };

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
      setRecordedDurationMs(null);
      await api.timeline(token, "recording_started", 0);
      setMessage("Идёт непрерывная запись 720p. Каждые 10 секунд видео отправляется в защищённое хранилище.");
    } catch {
      setMessage("Не удалось начать интервью. Если эта ссылка уже использовалась или интервью завершено, откройте новую ссылку. Иначе проверьте доступ к камере и микрофону.");
    }
  };
  useEffect(() => {
    if (stream && token && !autoStarted.current && !finished) {
      autoStarted.current = true;
      void start();
    }
  }, [stream, token, finished]);

  const saveAndContinue = async (timedOut = false) => {
    if (!token || !continuous.recording || submitting) return;
    const endOffsetMs = continuous.offset();
    if (endOffsetMs <= answerStartedAt) { setMessage("Запишите хотя бы несколько секунд ответа."); return; }
    if (!timedOut && question.kind === "coding" && !code.trim()) { setMessage("Добавьте кодовое решение перед сохранением ответа."); return; }
    setSubmitting(true);
    try {
      const segment = question.kind === "coding"
        ? await api.saveCodeAnswer(token, question.id, language, code, answerStartedAt, endOffsetMs, timedOut)
        : await api.saveSegment(token, question.id, answerStartedAt, endOffsetMs, timedOut);
      await api.timeline(token, "answer_saved", endOffsetMs, question.id);
      setAnswers((current) => ({ ...current, [question.id]: { responseId: segment.response_id, startOffsetMs: answerStartedAt, endOffsetMs, transcript: { status: segment.status, text: null } } }));
      // A temporary failure while checking for a future agent's follow-up must
      // never interrupt the candidate after their answer was safely saved.
      let updatedQuestions = questions;
      try {
        updatedQuestions = await refreshFollowUps();
      } catch {
        // The next refresh will pick up the queued clarification.
      }
      if (index < updatedQuestions.length - 1) {
        await api.timeline(token, "next_question_clicked", endOffsetMs, question.id);
        setIndex((current) => current + 1);
        setCode("");
        setMessage(timedOut ? "Время вопроса закончилось. Черновик сохранён, показан следующий вопрос." : "Следующий вопрос показан. Запись не прерывалась.");
      } else {
        setMessage("Все ответы сохранены. Завершите интервью, чтобы отправить единый видеофайл.");
      }
    } catch {
      setMessage("Не удалось сохранить границу ответа. Запись продолжается — попробуйте ещё раз.");
    } finally {
      setSubmitting(false);
    }
  };

  useEffect(() => {
    const limit = question.time_limit_seconds;
    if (!continuous.recording || !limit || answers[question.id]) return;
    const tick = () => {
      const offset = continuous.offset();
      setTimerOffsetMs(offset);
      if (offset - answerStartedAt >= limit * 1000 && !timedOutQuestions.current.has(question.id)) {
        timedOutQuestions.current.add(question.id);
        void saveAndContinue(true);
      }
    };
    tick();
    const interval = window.setInterval(tick, 250);
    return () => window.clearInterval(interval);
  }, [answerStartedAt, answers, continuous, question, saveAndContinue]);

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
      setRecordedDurationMs(endOffsetMs);
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

  if (finished) return <main className="preflight"><span className="interview-header__eyebrow">NAPOLEON [IT] · ASYNC INTERVIEW</span><h1>Интервью записано</h1><p>Спасибо за ответы. Видео, аудио и материалы coding-задач сохранены.</p><p>Ожидайте дальнейшей информации от рекрутера.</p></main>;
  return <main className="interview-shell">
    <header className="interview-header"><div><span className="interview-header__eyebrow">NAPOLEON IT · ASYNC INTERVIEW</span><h1>Техническое интервью</h1></div><span className="interview-header__recording">{continuous.recording ? "● Запись идёт" : finished ? "✓ Интервью завершено" : "Камера готова"}</span></header>
    {mediaError && <p role="alert">{mediaError}</p>}
    <nav className="block-progress" aria-label="Прогресс интервью">{Object.entries(blocks).map(([key, items]) => <div className="block-progress__item" key={key}><span>{items[0].block_title ?? key}</span><small>{items.filter((item) => answers[item.id]).length} / {items.length}</small><i style={{ width: `${items.filter((item) => answers[item.id]).length / items.length * 100}%` }} /></div>)}</nav>
    <section className={`interview-stage ${question.kind === "coding" ? "interview-stage--coding" : ""}`}>
      <CameraPreview stream={stream} />
      <div className="stage-topline"><span>ВАША КАМЕРА</span><span>{question.time_limit_seconds ? `Осталось ${Math.max(0, Math.ceil(question.time_limit_seconds - (timerOffsetMs - answerStartedAt) / 1000))} с · ` : ""}Вопрос {index + 1} / {questions.length}</span></div>
      {continuous.recording && <div className="question-overlay"><InterviewerAvatar compact speaking={speech.speaking} idleSrc={token ? api.questionAvatarFrameUrl(token, question.id, "idle") : undefined} speakingSrc={token ? api.questionAvatarFrameUrl(token, question.id, "speaking") : undefined} /><QuestionPlayer index={index} total={questions.length} text={question.text} isFollowUp={question.isFollowUp} onSpeak={() => void speakQuestion()} speaking={speech.speaking} /></div>}
      {continuous.recording && question.kind === "coding" && <CodeEditor language={language} source={code} onLanguage={setLanguage} onSource={setCode} />}
    </section>
    <section className="recording-controls"><div><p role="status">{message}</p>{continuous.recording && <span className="recording-controls__status">{Math.round(continuous.offset() / 1000)} с · сохранено фрагментов: {continuous.uploadedChunks}</span>}</div>{!continuous.recording && !finished && <button disabled={!stream || submitting} onClick={() => void start()}>Начать интервью</button>}{continuous.recording && !answers[question.id] && <button disabled={submitting} onClick={() => void saveAndContinue()}>{index === questions.length - 1 ? "Сохранить ответ" : "Сохранить и продолжить"}</button>}{continuous.recording && index === questions.length - 1 && allSaved && <button disabled={submitting} onClick={() => void finish()}>Завершить интервью</button>}</section>
    {debug && <section className="debug-panel" aria-label="Отладочная расшифровка"><h2>Отладка: расшифровка</h2><p>Буфер чанков в приложении: {(continuous.bufferedBytes / 1024 / 1024).toFixed(1)} MiB; пик: {(continuous.peakBufferedBytes / 1024 / 1024).toFixed(1)} MiB.</p><p>Время записи: {recordedDurationMs === null ? (continuous.recording ? formatDuration(continuous.offset()) : "ещё не завершена") : formatDuration(recordedDurationMs)}.</p>{questions.map((item, itemIndex) => <p key={item.id}>Вопрос {itemIndex + 1}: {debugTranscript(answers[item.id], finished, item)}</p>)}</section>}
  </main>;
}
