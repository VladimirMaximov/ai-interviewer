import { useEffect, useRef, useState } from "react";
import { AudioRecorder, RecordedAnswer, RecorderState } from "./AudioRecorder";
import { LiveCodingEditor } from "./LiveCodingEditor";
import { QuestionPlayer } from "./QuestionPlayer";
import { CandidateApi, InterviewQuestion } from "../../api/candidate";

const demoQuestions: InterviewQuestion[] = [
  { question_id: "00000000-0000-0000-0000-000000000001", prompt: "Расскажите о последнем проекте и вашей роли в нём.", kind: "baseline" },
  { question_id: "00000000-0000-0000-0000-000000000002", prompt: "Как вы обычно находите и устраняете сложную техническую проблему?", kind: "baseline" },
  { question_id: "00000000-0000-0000-0000-000000000003", prompt: "Какие технологии вы хотели бы применять в следующем проекте?", kind: "baseline" },
];

export function InterviewPage() {
  const [index, setIndex] = useState(0);
  const [questions, setQuestions] = useState<InterviewQuestion[]>(demoQuestions);
  const [answers, setAnswers] = useState<Record<string, RecordedAnswer>>({});
  const [liveCodingAnswers, setLiveCodingAnswers] = useState<Record<string, true>>({});
  const [planError, setPlanError] = useState<string | null>(null);
  const [recorderState, setRecorderState] = useState<RecorderState>("idle");
  const knownQuestionIds = useRef(new Set(demoQuestions.map((item) => item.question_id)));
  const token = new URLSearchParams(window.location.search).get("token");
  useEffect(() => {
    if (!token) return;
    const api = new CandidateApi();
    let active = true;
    const refreshQuestions = () => api.questions(token)
      .then((plan) => {
        if (!active) return;
        const newLiveCodingIndex = plan.questions.findIndex(
          (question) => question.kind === "live_coding" && !knownQuestionIds.current.has(question.question_id),
        );
        knownQuestionIds.current = new Set(plan.questions.map((item) => item.question_id));
        setQuestions(plan.questions);
        setIndex((current) => newLiveCodingIndex >= 0
          ? newLiveCodingIndex
          : Math.min(current, Math.max(0, plan.questions.length - 1)));
        setPlanError(null);
      })
      .catch(() => {
        if (active) setPlanError("План интервью пока недоступен. Попробуйте открыть ссылку позже.");
      });
    setAnswers({});
    setLiveCodingAnswers({});
    knownQuestionIds.current = new Set();
    setIndex(0);
    void refreshQuestions();
    const interval = window.setInterval(refreshQuestions, 3000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [token]);
  const currentQuestion = questions[index];
  const complete = questions.every((question) => question.kind === "live_coding"
    ? Boolean(liveCodingAnswers[question.question_id])
    : Boolean(answers[question.question_id]));
  const saveAnswer = (answer: RecordedAnswer) => setAnswers((current) => ({ ...current, [currentQuestion.question_id]: answer }));
  const clearAnswer = () => setAnswers((current) => {
    const next = { ...current };
    delete next[currentQuestion.question_id];
    return next;
  });
  const checksum = async (media: Blob) => {
    const digest = await crypto.subtle.digest("SHA-256", await media.arrayBuffer());
    return [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
  };
  const submit = async ({ audio, monitoringEvents }: RecordedAnswer) => {
    if (!token) return;
    const api = new CandidateApi();
    const grant = await api.uploadGrant(token, questions[index].question_id, audio.type || "audio/webm");
    await api.upload(grant.upload_url, audio);
    for (const event of monitoringEvents) {
      let evidenceContentType: string | undefined;
      let evidenceChecksum: string | undefined;
      if (event.evidence) {
        evidenceContentType = event.evidence.type || "video/webm";
        const evidenceGrant = await api.monitoringEvidenceGrant(
          token,
          event.client_event_id,
          grant.response_id,
          questions[index].question_id,
          evidenceContentType,
        );
        await api.upload(evidenceGrant.upload_url, event.evidence);
        evidenceChecksum = await checksum(event.evidence);
      }
      await api.recordMonitoringEvent(token, {
        client_event_id: event.client_event_id,
        response_id: grant.response_id,
        question_id: questions[index].question_id,
        kind: event.kind,
        started_at_ms: event.started_at_ms,
        ended_at_ms: event.ended_at_ms,
        confidence: event.confidence,
        detector_name: event.detector_name,
        detector_version: event.detector_version,
        evidence_content_type: evidenceContentType,
        evidence_checksum: evidenceChecksum,
      });
    }
    await api.confirm(token, grant.response_id, await checksum(audio));
  };
  const submitLiveCoding = async (code: string) => {
    if (token) {
      await new CandidateApi().submitLiveCoding(
        token,
        currentQuestion.question_id,
        code,
      );
    }
    setLiveCodingAnswers((current) => ({
      ...current,
      [currentQuestion.question_id]: true,
    }));
  };

  if (planError) return <main><h1>Техническое интервью</h1><p role="alert">{planError}</p></main>;
  if (questions.length === 0) return <main><h1>Техническое интервью</h1><p>План интервью готовится.</p></main>;

  return <main><h1>Техническое интервью</h1>{!token && <p>Демо-режим: аудио не отправляется на сервер.</p>}{currentQuestion.kind === "follow_up" && <p>Уточняющий вопрос по вашему предыдущему ответу.</p>}{currentQuestion.kind === "live_coding"
    ? <LiveCodingEditor key={currentQuestion.question_id} prompt={currentQuestion.prompt} onSubmit={submitLiveCoding} />
    : <><QuestionPlayer index={index} total={questions.length} text={currentQuestion.prompt} /><AudioRecorder key={currentQuestion.question_id} onRecorded={saveAnswer} onCleared={clearAnswer} onSubmit={token ? submit : undefined} onStateChange={setRecorderState} /><p>{answers[currentQuestion.question_id] ? "Ответ сохранён в браузере до отправки." : "Ответ ещё не записан."}</p></>}
    <button disabled={index === 0 || recorderState === "recording"} onClick={() => setIndex(index - 1)}>Предыдущий</button>
    <button disabled={index === questions.length - 1 || recorderState === "recording"} onClick={() => setIndex(index + 1)}>Следующий</button>
    {index === questions.length - 1 && <button disabled={!complete} onClick={() => alert("Все ответы готовы к безопасной отправке.")}>Сохранить интервью</button>}
  </main>;
}
