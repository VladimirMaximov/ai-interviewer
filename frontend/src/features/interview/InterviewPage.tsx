import { useEffect, useState } from "react";
import { AudioRecorder } from "./AudioRecorder";
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
  const [answers, setAnswers] = useState<(Blob | null)[]>(Array(demoQuestions.length).fill(null));
  const [planError, setPlanError] = useState<string | null>(null);
  const token = new URLSearchParams(window.location.search).get("token");
  useEffect(() => {
    if (!token) return;
    const api = new CandidateApi();
    api.questions(token)
      .then((plan) => {
        setQuestions(plan.questions);
        setAnswers(Array(plan.questions.length).fill(null));
        setIndex(0);
      })
      .catch(() => setPlanError("План интервью пока недоступен. Попробуйте открыть ссылку позже."));
  }, [token]);
  const complete = answers.every(Boolean);
  const saveAnswer = (audio: Blob) => setAnswers((current) => current.map((answer, i) => i === index ? audio : answer));
  const clearAnswer = () => setAnswers((current) => current.map((answer, i) => i === index ? null : answer));
  const submit = async (audio: Blob) => {
    if (!token) return;
    const api = new CandidateApi();
    const grant = await api.uploadGrant(token, questions[index].question_id, audio.type || "audio/webm");
    await api.upload(grant.upload_url, audio);
    const digest = await crypto.subtle.digest("SHA-256", await audio.arrayBuffer());
    const checksum = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
    await api.confirm(token, grant.response_id, checksum);
  };

  if (planError) return <main><h1>Техническое интервью</h1><p role="alert">{planError}</p></main>;
  if (questions.length === 0) return <main><h1>Техническое интервью</h1><p>План интервью готовится.</p></main>;

  return <main><h1>Техническое интервью</h1>{!token && <p>Демо-режим: аудио не отправляется на сервер.</p>}<QuestionPlayer index={index} total={questions.length} text={questions[index].prompt} /><AudioRecorder onRecorded={saveAnswer} onCleared={clearAnswer} onSubmit={token ? submit : undefined} />
    <p>{answers[index] ? "Ответ сохранён в браузере до отправки." : "Ответ ещё не записан."}</p>
    <button disabled={index === 0} onClick={() => setIndex(index - 1)}>Предыдущий</button>
    <button disabled={index === questions.length - 1} onClick={() => setIndex(index + 1)}>Следующий</button>
    {index === questions.length - 1 && <button disabled={!complete} onClick={() => alert("Все ответы готовы к безопасной отправке.")}>Сохранить интервью</button>}
  </main>;
}
