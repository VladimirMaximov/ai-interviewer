import { createRoot } from "react-dom/client";
import { StrictMode } from "react";
import { useState } from "react";
import { ConsentScreen } from "./features/interview/ConsentScreen";
import { InterviewPage } from "./features/interview/InterviewPage";
import { CandidateApi } from "./api/candidate";
import "./styles.css";

const App = () => {
  const [consented, setConsented] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const accept = async () => { try { const token = new URLSearchParams(window.location.search).get("token"); if (token) await new CandidateApi().consent(token); setConsented(true); } catch { setError("Не удалось начать интервью. Обновите страницу и попробуйте ещё раз."); } };
  if (error) return <main><p role="alert">{error}</p><button onClick={() => setError(null)}>Повторить</button></main>;
  return consented ? <InterviewPage /> : <ConsentScreen onAccept={accept} />;
};

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
