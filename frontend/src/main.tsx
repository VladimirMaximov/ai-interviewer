import { createRoot } from "react-dom/client";
import { StrictMode } from "react";

const App = () => <main><h1>AI Interviewer</h1><p>Interview recording is being prepared.</p></main>;

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
