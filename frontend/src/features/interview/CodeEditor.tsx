import Editor from "@monaco-editor/react";

type Props = { language: string; source: string; onLanguage: (value: string) => void; onSource: (value: string) => void };

export function CodeEditor({ language, source, onLanguage, onSource }: Props) {
  return <section className="code-editor" aria-label="Редактор кода"><header><strong>Решение</strong><label>Язык <select value={language} onChange={(event) => onLanguage(event.target.value)}><option>Python</option><option>JavaScript</option><option>TypeScript</option><option>Java</option><option>Go</option></select></label></header><Editor height="330px" language={language.toLowerCase() === "javascript" ? "javascript" : language.toLowerCase()} theme="vs-dark" value={source} onChange={(value) => onSource(value ?? "")} options={{ minimap: { enabled: false }, fontSize: 14, padding: { top: 14 }, automaticLayout: true, scrollBeyondLastLine: false }} /><footer>Камера и микрофон продолжают записывать ход решения.</footer></section>;
}
