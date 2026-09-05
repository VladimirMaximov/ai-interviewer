import { createRoot } from "react-dom/client";
import { StrictMode } from "react";
import { useEffect, useState } from "react";
import { ConsentScreen } from "./features/interview/ConsentScreen";
import { InterviewPage } from "./features/interview/InterviewPage";
import { CandidateApi, CandidateQuestion, Invitation } from "./api/candidate";
import "@ai-interviewer/brand-tokens/src/tokens.css";
import "./styles.css";

const App = () => {
  const [consented, setConsented] = useState(false);
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [preview, setPreview] = useState<CandidateQuestion[]>([]);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { const token = new URLSearchParams(window.location.search).get("token"); if (token) void new CandidateApi().resolve(token).then((value) => setPreview(value.questions)).catch(() => setError("Ссылка интервью недоступна.")); }, []);
  const accept = async (stream: MediaStream) => { try { const token = new URLSearchParams(window.location.search).get("token"); if (!token) throw new Error("missing token"); const resolved = await new CandidateApi().consent(token); setMediaStream(stream); setInvitation(resolved); setConsented(true); } catch { stream.getTracks().forEach((track) => track.stop()); setError("Не удалось начать интервью. Обновите страницу и попробуйте ещё раз."); } };
  if (error) return <main><p role="alert">{error}</p><button onClick={() => setError(null)}>Повторить</button></main>;
  return consented && invitation ? <InterviewPage baseQuestions={invitation.questions} initialStream={mediaStream} /> : <ConsentScreen onAccept={accept} questions={preview} />;
};

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
