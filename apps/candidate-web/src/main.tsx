import { createRoot } from "react-dom/client";
import { StrictMode } from "react";
import { useEffect, useState } from "react";
import { ConsentScreen } from "./features/interview/ConsentScreen";
import { InterviewPage } from "./features/interview/InterviewPage";
import { CandidateApi, CandidateQuestion, Invitation } from "./api/candidate";
import "@ai-interviewer/brand-tokens/src/tokens.css";
import "./styles.css";

const ProfileScreen = ({ onSubmit, initialAlias = "" }: { onSubmit: (alias: string, resume: string) => Promise<void>; initialAlias?: string }) => {
  const [alias, setAlias] = useState(initialAlias);
  const [resume, setResume] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!alias.trim() || !resume.trim()) { setMessage("Укажите имя и вставьте текст резюме."); return; }
    setSaving(true); setMessage("");
    try { await onSubmit(alias.trim(), resume.trim()); } catch { setMessage("Не удалось сохранить данные. Проверьте ссылку и повторите попытку."); } finally { setSaving(false); }
  };
  return <main className="preflight profile-screen"><div className="profile-screen__intro"><span className="interview-header__eyebrow">NAPOLEON [IT] · ASYNC INTERVIEW</span><span className="profile-screen__step">Шаг 1 из 2</span><h1>Расскажите немного о себе</h1><p>Имя увидит рекрутер, а резюме поможет подобрать вопросы под ваш опыт. Перед отправкой вы сможете проверить введённые данные.</p><div className="profile-screen__privacy"><strong>Ваши данные защищены</strong><span>Используем их только для этого интервью.</span></div></div><form className="profile-form" onSubmit={(event) => void submit(event)}><div className="profile-field"><label htmlFor="candidate-alias">Имя или псевдоним</label><span>Как к вам обращаться в отчёте</span><input id="candidate-alias" value={alias} onChange={(event) => setAlias(event.target.value)} maxLength={120} required placeholder="Например, Алексей" /></div><div className="profile-field"><label htmlFor="candidate-resume">Резюме</label><span>Вставьте текст — форматирование не обязательно</span><textarea id="candidate-resume" value={resume} onChange={(event) => setResume(event.target.value)} maxLength={20000} rows={10} required placeholder={"Опыт работы, проекты, технологии и образование…"} /></div>{message && <p className="profile-form__error" role="alert">{message}</p>}<button className="profile-form__submit" disabled={saving}>{saving ? "Сохраняем…" : "Продолжить к проверке оборудования →"}</button></form></main>;
};

const ExistingSessionScreen = ({ completed }: { completed: boolean }) => <main className="preflight preflight--complete"><span className="interview-header__eyebrow">NAPOLEON [IT] · ASYNC INTERVIEW</span><span className="completion-mark" aria-hidden="true">{completed ? "✓" : "…"}</span><h1>{completed ? "Интервью уже завершено" : "Интервью уже начато"}</h1><p>{completed ? "Эта ссылка уже использована. Повторная запись не создаётся, а результат доступен рекрутеру." : "По этой ссылке уже есть активная сессия. Откройте исходную вкладку, чтобы продолжить, или запросите новую ссылку у рекрутера."}</p></main>;

const App = () => {
  const [consented, setConsented] = useState(false);
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [preview, setPreview] = useState<CandidateQuestion[]>([]);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [profileSaved, setProfileSaved] = useState(false);
  useEffect(() => { const token = new URLSearchParams(window.location.search).get("token"); if (token) void new CandidateApi().resolve(token).then((value) => { setInvitation(value); setPreview(value.questions); }).catch(() => setError("Ссылка интервью недоступна.")); }, []);
  const accept = async (stream: MediaStream) => { try { const token = new URLSearchParams(window.location.search).get("token"); if (!token) throw new Error("missing token"); const resolved = await new CandidateApi().consent(token); setMediaStream(stream); setInvitation(resolved); setConsented(true); } catch { stream.getTracks().forEach((track) => track.stop()); setError("Не удалось начать интервью. Обновите страницу и попробуйте ещё раз."); } };
  const saveProfile = async (alias: string, resume: string) => { const token = new URLSearchParams(window.location.search).get("token"); if (!token) throw new Error("missing token"); const resolved = await new CandidateApi().saveProfile(token, alias, resume); setInvitation(resolved); setProfileSaved(true); };
  if (error) return <main><p role="alert">{error}</p><button onClick={() => setError(null)}>Повторить</button></main>;
  if (consented && invitation) return <InterviewPage baseQuestions={invitation.questions} initialStream={mediaStream} />;
  if (invitation?.completed) return <ExistingSessionScreen completed />;
  if (invitation?.in_progress) return <ExistingSessionScreen completed={false} />;
  if (invitation && !invitation.resume_uploaded && !profileSaved) return <ProfileScreen onSubmit={saveProfile} initialAlias={invitation.candidate_alias ?? ""} />;
  return <ConsentScreen onAccept={accept} questions={preview} />;
};

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
