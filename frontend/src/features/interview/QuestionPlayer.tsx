type QuestionPlayerProps = { index: number; total: number; text: string };

export function QuestionPlayer({ index, total, text }: QuestionPlayerProps) {
  return <section aria-live="polite"><p>Вопрос {index + 1} из {total}</p><h2>{text}</h2><p>Прочитайте вопрос и запишите ответ в удобном темпе.</p></section>;
}
