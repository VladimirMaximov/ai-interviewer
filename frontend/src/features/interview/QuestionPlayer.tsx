type QuestionPlayerProps = { index: number; total: number; text: string; isFollowUp?: boolean; onSpeak: () => void; speaking: boolean };

export function QuestionPlayer({ index, total, text, isFollowUp = false, onSpeak, speaking }: QuestionPlayerProps) {
  return <section className="question-card" aria-live="polite"><div className="question-card__meta"><span>{isFollowUp ? "Уточняющий вопрос" : `Вопрос ${index + 1} из ${total}`}</span><button className="button--quiet" onClick={onSpeak}>{speaking ? "Вопрос озвучивается" : "↻ Повторить вопрос"}</button></div><h2>{text}</h2><p>{isFollowUp ? "Этот вопрос необязательный и помогает уточнить ваш предыдущий ответ." : "Ответьте в удобном темпе. Запись видео и звука продолжается автоматически."}</p></section>;
}
