import { CandidateFeedback, FeedbackEvidence } from "../../api/candidate";


const alignmentLabels = {
  confirmed: "Подтверждено",
  partially_confirmed: "Подтверждено частично",
  not_confirmed: "Не подтверждено в интервью",
  not_assessed: "Не оценивалось",
};


function EvidenceQuotes({ evidence }: { evidence: FeedbackEvidence[] }) {
  const excerpts = evidence.flatMap((item) => item.excerpt ? [item.excerpt] : []);
  if (excerpts.length === 0) return null;
  return <div aria-label="Фрагменты ваших ответов">
    {excerpts.map((excerpt) => <blockquote key={excerpt}>«{excerpt}»</blockquote>)}
  </div>;
}


export function CandidateFeedbackPage({ feedback }: { feedback: CandidateFeedback }) {
  return <main>
    <p>Обратная связь по видеоинтервью</p>
    <h1>{feedback.headline}</h1>
    {feedback.score.value !== null && <section aria-label="Результат интервью">
      <h2>{feedback.score.value.toLocaleString("ru-RU")} из {feedback.score.maximum}</h2>
      <p>{feedback.score.explanation}</p>
    </section>}
    <p>{feedback.summary}</p>

    <section>
      <h2>Что было хорошо</h2>
      {feedback.strengths.length === 0 ? <p>По этому интервью недостаточно данных для вывода.</p> : <ul>
        {feedback.strengths.map((item) => <li key={item.title}>
          <strong>{item.title}.</strong> {item.detail}
          <EvidenceQuotes evidence={item.evidence} />
        </li>)}
      </ul>}
    </section>

    <section>
      <h2>Что стоит усилить</h2>
      <ul>{feedback.growth_areas.map((item) => <li key={item.title}>
        <strong>{item.title}.</strong> {item.detail}<br />
        <span>Практический шаг: {item.action}</span>
        <EvidenceQuotes evidence={item.evidence} />
      </li>)}</ul>
    </section>

    {feedback.experience_alignment.length > 0 && <section>
      <h2>Соответствие опыта</h2>
      <ul>{feedback.experience_alignment.map((item) => <li key={`${item.status}-${item.title}`}>
        <strong>{alignmentLabels[item.status]} — {item.title}.</strong> {item.detail}
        <EvidenceQuotes evidence={item.evidence} />
      </li>)}</ul>
    </section>}

    {feedback.alternative_vacancy && <section>
      <h2>Возможно, вам подойдёт другая вакансия</h2>
      <h3>{feedback.alternative_vacancy.title}</h3>
      <p>{feedback.alternative_vacancy.message}</p>
      <p>Совпавшие направления: {feedback.alternative_vacancy.matched_areas.join(", ")}.</p>
    </section>}

    <section>
      <h2>Следующие шаги</h2>
      <ul>{feedback.next_steps.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>

    <details>
      <summary>Ограничения оценки</summary>
      <ul>{feedback.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
    </details>
  </main>;
}
