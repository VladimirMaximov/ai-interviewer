import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { listInterviewResults } from '../api';
import { InterviewResultSummary } from '../types';

const labels: Record<InterviewResultSummary['status'], string> = { invited: 'Ожидает кандидата', in_progress: 'Интервью идёт', processing: 'Обработка', completed: 'Готово' };

const Leaderboard: React.FC = () => {
  const { vacancyId = '' } = useParams();
  const navigate = useNavigate();
  const [items, setItems] = useState<InterviewResultSummary[]>([]);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  useEffect(() => { setState('loading'); listInterviewResults(vacancyId).then((value) => { setItems(value); setState('ready'); }).catch(() => setState('error')); }, [vacancyId]);
  return <><nav className="navbar navbar-light bg-white shadow-sm"><div className="container"><span className="navbar-brand">AI Интервьюер</span><button className="btn btn-sm btn-outline-secondary" onClick={() => navigate('/homepage')}>← Назад</button></div></nav><main className="container my-4" style={{ maxWidth: 1200 }}><section className="card shadow-sm"><div className="card-header bg-white py-3"><h4 className="mb-1">Интервью по вакансии</h4><div className="text-muted">Реальные сессии и сохранённые материалы</div></div><div className="card-body p-0 table-responsive">
    {state === 'loading' && <p className="p-4 text-muted">Загружаем интервью…</p>}
    {state === 'error' && <p className="p-4 text-danger" role="alert">Не удалось загрузить интервью.</p>}
    {state === 'ready' && !items.length && <div className="p-5 text-center"><h5>Интервью пока нет</h5><p className="text-muted mb-0">Создайте ссылку кандидату — сессия появится здесь автоматически.</p></div>}
    {!!items.length && <table className="table table-hover align-middle mb-0"><thead className="table-light"><tr><th>Кандидат</th><th>Статус</th><th>Ответы</th><th>Оценка</th><th>Завершено</th></tr></thead><tbody>{items.map((item) => <tr key={item.invitation_id} role={item.session_id ? 'button' : undefined} onClick={() => item.session_id && navigate(`/leaderboard/${vacancyId}/candidate/${item.session_id}`)}><td><strong>{item.candidate_alias || 'Кандидат без имени'}</strong></td><td><span className={`badge ${item.status === 'completed' ? 'bg-success' : item.status === 'processing' ? 'bg-warning text-dark' : 'bg-secondary'}`}>{labels[item.status]}</span></td><td>{item.answered_questions} / {item.total_questions}</td><td>{item.score === null ? <span className="text-muted">Не рассчитана</span> : `${item.score}%`}</td><td>{item.submitted_at ? new Date(item.submitted_at).toLocaleString('ru-RU') : '—'}</td></tr>)}</tbody></table>}
  </div></section></main></>;
};
export default Leaderboard;
