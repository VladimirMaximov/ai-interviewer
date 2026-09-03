import { useState } from "react";
import { AudioRecorder } from "./AudioRecorder";
import { QuestionPlayer } from "./QuestionPlayer";
import { CandidateApi } from "../../api/candidate";

const questions = ["Расскажите о последнем проекте и вашей роли в нём.", "Как вы обычно находите и устраняете сложную техническую проблему?", "Какие технологии вы хотели бы применять в следующем проекте?"];

export function InterviewPage() {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<(Blob | null)[]>(Array(questions.length).fill(null));
  const complete = answers.every(Boolean);
  const saveAnswer = (audio: Blob) => setAnswers((current) => current.map((answer, i) => i === index ? audio : answer));
  const clearAnswer = () => setAnswers((current) => current.map((answer, i) => i === index ? null : answer));
  const token = new URLSearchParams(window.location.search).get("token");
  const submit = async (audio: Blob) => {
    if (!token) return;
    const api = new CandidateApi();
    const grant = await api.uploadGrant(token, crypto.randomUUID(), audio.type || "audio/webm");
    await api.upload(grant.upload_url, audio);
    const digest = await crypto.subtle.digest("SHA-256", await audio.arrayBuffer());
    const checksum = [...new Uint8Array(digest)].map((value) => value.toString(16).padStart(2, "0")).join("");
    await api.confirm(token, grant.response_id, checksum);
  };

  return <main><h1>Техническое интервью</h1>{!token && <p>Демо-режим: аудио не отправляется на сервер.</p>}<QuestionPlayer index={index} total={questions.length} text={questions[index]} /><AudioRecorder onRecorded={saveAnswer} onCleared={clearAnswer} onSubmit={token ? submit : undefined} />
    <p>{answers[index] ? "Ответ сохранён в браузере до отправки." : "Ответ ещё не записан."}</p>
    <button disabled={index === 0} onClick={() => setIndex(index - 1)}>Предыдущий</button>
    <button disabled={index === questions.length - 1} onClick={() => setIndex(index + 1)}>Следующий</button>
    {index === questions.length - 1 && <button disabled={!complete} onClick={() => alert("Все ответы готовы к безопасной отправке.")}>Сохранить интервью</button>}
  </main>;
}
