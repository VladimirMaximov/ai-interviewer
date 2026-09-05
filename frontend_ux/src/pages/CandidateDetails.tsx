import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { CandidateResult, MOCK_CANDIDATES } from './Leaderboard';

const MOCK_TRANSCRIPT = [
  ['ИИ-интервьюер', 'Расскажите о вашем опыте разработки на Python.'],
  ['Кандидат', 'Последние четыре года я разрабатываю backend-сервисы на Python. Работала с FastAPI, Django, PostgreSQL и Redis.'],
  ['ИИ-интервьюер', 'Как вы обеспечиваете качество и надёжность кода?'],
  ['Кандидат', 'Пишу unit- и интеграционные тесты, использую type hints, линтеры и обязательный code review. Для критичных сценариев добавляю метрики и алерты.'],
  ['ИИ-интервьюер', 'Как бы вы диагностировали медленный API endpoint?'],
  ['Кандидат', 'Начала бы с метрик времени ответа и трассировки, затем проверила запросы к базе, внешние вызовы и профилирование CPU. После этого сравнила бы результат до и после оптимизации.'],
];

const CandidateDetails: React.FC = () => {
  const { vacancyId, candidateId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const candidate = (location.state as { candidate?: CandidateResult } | null)?.candidate
    || MOCK_CANDIDATES.find((item) => item.id === candidateId)
    || MOCK_CANDIDATES[0];
  const [vacancyTitle, setVacancyTitle] = useState('Middle Python разработчик');

  useEffect(() => {
    if (!localStorage.getItem('user')) { navigate('/login'); return; }
    api.get(`/vacancies/${vacancyId}`)
      .then((response) => setVacancyTitle(response.data?.title || 'Middle Python разработчик'))
      .catch(() => undefined);
  }, [navigate, vacancyId]);

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand">AI Интервьюер</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => navigate(`/leaderboard/${vacancyId}`)}>← К лидерборду</button>
        </div>
      </nav>
      <main className="container my-4" style={{ maxWidth: 1150 }}>
        <section className="card shadow-sm mb-4">
          <div className="card-body d-flex flex-wrap justify-content-between align-items-center gap-3">
            <div><div className="text-muted small">Кандидат</div><h4 className="mb-0">{candidate.name}</h4></div>
            <div><div className="text-muted small">Вакансия</div><strong>{vacancyTitle}</strong></div>
            <span className="badge bg-primary fs-6">Оценка: {candidate.score}%</span>
          </div>
        </section>
        <section className="card shadow-sm mb-4">
          <div className="card-body">
            <p className="mb-2">Кандидат показал уверенное владение Python и практический опыт разработки backend-сервисов. Ответы структурированы, технические решения объясняет через измеримые сигналы и проверяемые гипотезы.</p>
            <p className="mb-0 text-muted">Сильные стороны: архитектурное мышление, тестирование и диагностика производительности. На следующем этапе рекомендуется уточнить опыт проектирования высоконагруженных систем.</p>
          </div>
        </section>
        <div className="row g-4">
          <div className="col-lg-5">
            <section className="card shadow-sm h-100"><div className="card-body">
              <h5>Видеозапись интервью</h5>
              <div className="bg-dark text-white rounded d-flex flex-column align-items-center justify-content-center" style={{ aspectRatio: '16 / 9', minHeight: 220 }}>
                <div style={{ fontSize: 52 }}>▶</div><div>Демо-видео интервью</div><small className="text-white-50">00:34:18</small>
              </div>
            </div></section>
          </div>
          <div className="col-lg-7">
            <section className="card shadow-sm h-100"><div className="card-body">
              <h5>Полный транскрипт интервью</h5>
              <div className="overflow-auto pe-2" style={{ maxHeight: 430 }}>
                {MOCK_TRANSCRIPT.map(([speaker, text], index) => (
                  <div className="mb-3" key={index}><strong className={speaker === 'Кандидат' ? 'text-primary' : 'text-secondary'}>{speaker}</strong><div>{text}</div></div>
                ))}
              </div>
            </div></section>
          </div>
        </div>
      </main>
    </>
  );
};

export default CandidateDetails;
