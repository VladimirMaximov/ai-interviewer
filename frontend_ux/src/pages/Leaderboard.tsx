import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';

export interface CandidateResult {
  id: string;
  name: string;
  score: number;
  soft_skills?: number;
  experience?: number;
  hard_skills?: number;
  status: string;
  comment: string;
  date: string;
}

export const MOCK_CANDIDATES: CandidateResult[] = [
  { id: 'candidate-1', name: 'Анна Смирнова', score: 92, soft_skills: 9, experience: 9, hard_skills: 9, status: '', comment: 'Сильный Python и уверенное понимание архитектуры.', date: '15.08.2026' },
  { id: 'candidate-2', name: 'Михаил Кузнецов', score: 84, soft_skills: 8, experience: 5, hard_skills: 8, status: '', comment: 'Хорошая база, стоит глубже проверить опыт с очередями.', date: '14.08.2026' },
  { id: 'candidate-3', name: 'Екатерина Петрова', score: 78, soft_skills: 5, experience: 8, hard_skills: 5, status: '', comment: 'Уверенно решает практические задачи и ясно рассуждает.', date: '13.08.2026' },
];

const Leaderboard: React.FC = () => {
  const { vacancyId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<CandidateResult[]>(MOCK_CANDIDATES);
  const [sentIds, setSentIds] = useState<string[]>([]);
  const [filters, setFilters] = useState({
    name: '', score: '', soft_skills: '', experience: '', hard_skills: '',
    comment: '', date: '', sent: ''
  });

  useEffect(() => {
    if (!localStorage.getItem('user')) { navigate('/login'); return; }
    api.get(`/leaderboard/${vacancyId}`)
      .then((response) => {
        if (!response.data?.length) return;
        setData(response.data.map((item: any, index: number) => ({
          id: item.id || item.candidate_id || `candidate-${index + 1}`,
          name: item.name,
          score: item.score,
          soft_skills: item.soft_skills,
          experience: item.experience,
          hard_skills: item.hard_skills,
          status: item.status || '',
          comment: item.comment || '—',
          date: item.date || '—',
        })));
      })
      .catch(() => setData(MOCK_CANDIDATES));
  }, [navigate, vacancyId]);

  const openCandidate = (candidate: CandidateResult) => {
    navigate(`/leaderboard/${vacancyId}/candidate/${candidate.id}`, { state: { candidate } });
  };

  const sendToManager = (event: React.MouseEvent, candidateId: string) => {
    event.stopPropagation();
    setSentIds((current) => current.includes(candidateId) ? current : [...current, candidateId]);
  };

  const updateFilter = (field: keyof typeof filters, value: string) => {
    setFilters((current) => ({ ...current, [field]: value }));
  };

  const filteredData = data.filter((item) => {
    const contains = (value: string | number | undefined, query: string) =>
      String(value ?? '').toLowerCase().includes(query.toLowerCase());
    const atLeast = (value: number | undefined, query: string) =>
      !query || (value !== undefined && value >= Number(query));
    const isSent = sentIds.includes(item.id);
    return contains(item.name, filters.name)
      && atLeast(item.score, filters.score)
      && atLeast(item.soft_skills, filters.soft_skills)
      && atLeast(item.experience, filters.experience)
      && atLeast(item.hard_skills, filters.hard_skills)
      && contains(item.comment, filters.comment)
      && contains(item.date, filters.date)
      && (!filters.sent || (filters.sent === 'sent') === isSent);
  });

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand">AI Интервьюер</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => navigate('/homepage')}>← Назад</button>
        </div>
      </nav>
      <div className="container mt-4" style={{ maxWidth: 1400 }}>
        <div className="card shadow-sm">
          <div className="card-header bg-white text-center py-3"><h5 className="mb-0">Лидерборд</h5></div>
          <div className="card-body p-0 table-responsive">
            <table className="table table-hover align-middle mb-0">
              <thead className="table-light">
                <tr><th>#</th><th>ФИО</th><th>Оценка</th><th className="text-center text-nowrap">Soft skills</th><th className="text-center text-nowrap">Опыт</th><th className="text-center text-nowrap">Hard skills</th><th>Комментарий</th><th>Дата</th><th>Действие</th></tr>
                <tr className="filter-row">
                  <th></th>
                  <th><input className="form-control form-control-sm" value={filters.name} onChange={(event) => updateFilter('name', event.target.value)} placeholder="ФИО" /></th>
                  <th><input className="form-control form-control-sm" type="number" min="0" max="100" value={filters.score} onChange={(event) => updateFilter('score', event.target.value)} placeholder="От" /></th>
                  <th><input className="form-control form-control-sm" type="number" min="0" max="10" value={filters.soft_skills} onChange={(event) => updateFilter('soft_skills', event.target.value)} placeholder="От 0" /></th>
                  <th><input className="form-control form-control-sm" type="number" min="0" max="10" value={filters.experience} onChange={(event) => updateFilter('experience', event.target.value)} placeholder="От 0" /></th>
                  <th><input className="form-control form-control-sm" type="number" min="0" max="10" value={filters.hard_skills} onChange={(event) => updateFilter('hard_skills', event.target.value)} placeholder="От 0" /></th>
                  <th><input className="form-control form-control-sm" value={filters.comment} onChange={(event) => updateFilter('comment', event.target.value)} placeholder="Текст" /></th>
                  <th><input className="form-control form-control-sm" value={filters.date} onChange={(event) => updateFilter('date', event.target.value)} placeholder="Дата" /></th>
                  <th><select className="form-select form-select-sm" value={filters.sent} onChange={(event) => updateFilter('sent', event.target.value)}><option value="">Все</option><option value="sent">Отправлено</option><option value="not_sent">Не отправлено</option></select></th>
                </tr>
              </thead>
              <tbody>
                {filteredData.map((item, index) => {
                  const isSent = sentIds.includes(item.id);
                  return (
                    <tr key={item.id} role="button" onClick={() => openCandidate(item)} title="Открыть карточку кандидата">
                      <td>{index + 1}</td>
                      <td><strong>{item.name}</strong></td>
                      <td><span className="badge bg-primary">{item.score}%</span></td>
                      {(['soft_skills', 'experience', 'hard_skills'] as const).map((field) => (
                        <td key={field} className="text-center">
                          <span
                            className={`badge fs-6 ${item[field] === undefined ? 'bg-secondary' : 'bg-primary'}`}
                            aria-label={item[field] === undefined ? 'Нет данных' : `${item[field]} из 10`}
                          >{item[field] === undefined ? '—' : item[field]}</span>
                        </td>
                      ))}
                      <td>{item.comment}</td><td>{item.date}</td>
                      <td><button className={`btn btn-sm ${isSent ? 'btn-success' : 'btn-outline-primary'}`} onClick={(event) => sendToManager(event, item.id)} disabled={isSent}>{isSent ? 'Отправлено' : 'Отправить менеджеру'}</button></td>
                    </tr>
                  );
                })}
                {!filteredData.length && <tr><td colSpan={9} className="text-center text-muted py-4">По выбранным фильтрам кандидатов нет</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
};

export default Leaderboard;
