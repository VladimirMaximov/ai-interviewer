import { useState } from "react";

type LiveCodingEditorProps = {
  prompt: string;
  onSubmit: (code: string) => Promise<void>;
};

export function LiveCodingEditor({ prompt, onSubmit }: LiveCodingEditorProps) {
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (code.trim().length < 4 || submitting || submitted) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit(code);
      setSubmitted(true);
    } catch {
      setError("Не удалось отправить решение. Проверьте соединение и попробуйте ещё раз.");
    } finally {
      setSubmitting(false);
    }
  };

  return <section aria-label="Лайв-кодинг">
    <h2>Лайв-кодинг</h2>
    <p>Эта секция появляется не более одного раза за интервью. Решение будет оценено вместе с остальными ответами.</p>
    <pre>{prompt}</pre>
    <label htmlFor="live-coding-solution">Ваше решение</label>
    <textarea
      id="live-coding-solution"
      rows={18}
      value={code}
      onChange={(event) => setCode(event.target.value)}
      disabled={submitting || submitted}
      spellCheck={false}
      autoCapitalize="off"
      autoCorrect="off"
    />
    <button disabled={code.trim().length < 4 || submitting || submitted} onClick={() => void submit()}>
      {submitting ? "Отправляем…" : submitted ? "Решение отправлено" : "Отправить решение"}
    </button>
    {error && <p role="alert">{error}</p>}
  </section>;
}
