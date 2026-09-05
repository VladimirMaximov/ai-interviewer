import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { createInvitation, listVacancies } from '../api';
import { Vacancy } from '../types';

const Homepage: React.FC = () => {
  const location = useLocation();
  const createdVacancy = location.state?.createdVacancy as Vacancy | undefined;
  const [vacancies, setVacancies] = useState<Vacancy[]>(createdVacancy ? [createdVacancy] : []);
  const [loadError, setLoadError] = useState('');
  const [creatingFor, setCreatingFor] = useState<string | null>(null);
  const [invitationUrls, setInvitationUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    listVacancies().then((loaded) => {
      setVacancies(loaded);
      setLoadError('');
    }).catch(() => setLoadError('Не удалось загрузить вакансии из основного сервиса.'));
  }, []);

  const issueInvitation = async (vacancyId: string) => {
    try {
      setCreatingFor(vacancyId);
      const invitation = await createInvitation(vacancyId);
      setInvitationUrls((current) => ({ ...current, [vacancyId]: invitation.candidate_url }));
    } catch {
      setLoadError('Не удалось создать ссылку. Проверьте конфигурацию интервью.');
    } finally {
      setCreatingFor(null);
    }
  };

  const copyLink = async (url: string) => {
    await navigator.clipboard.writeText(url);
  };

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container"><span className="navbar-brand">AI Интервьюер</span><span className="badge bg-secondary">Демо-кабинет</span></div>
      </nav>
      <main className="container my-4" style={{ maxWidth: 980 }}>
        {createdVacancy && <div className="alert alert-success">Вакансия «{createdVacancy.title}» сохранена.</div>}
        {loadError && <div className="alert alert-warning">{loadError}</div>}
        <div className="d-flex justify-content-between align-items-center mb-3"><h1 className="h4 mb-0">Вакансии</h1><Link to="/vacancy/new" className="btn btn-primary">Новая вакансия</Link></div>
        {!vacancies.length && !loadError && <div className="card p-4 text-center text-muted">Пока нет вакансий.</div>}
        {vacancies.map((vacancy) => (
          <section key={vacancy.id} className="card shadow-sm mb-3">
            <div className="card-body">
              <div className="d-flex flex-wrap justify-content-between gap-3">
                <div><h2 className="h5 mb-1">{vacancy.title}</h2><small className="text-muted">{vacancy.status === 'active' ? 'Активна' : 'Закрыта'}</small></div>
                <div className="d-flex gap-2"><Link to={`/vacancy/${vacancy.id}`} className="btn btn-outline-secondary">Вопросы</Link><Link to={`/leaderboard/${vacancy.id}`} className="btn btn-outline-primary">Результаты</Link><button className="btn btn-primary" disabled={creatingFor === vacancy.id} onClick={() => issueInvitation(vacancy.id)}>{creatingFor === vacancy.id ? 'Создаём…' : 'Создать ссылку'}</button></div>
              </div>
              {invitationUrls[vacancy.id] && <div className="input-group mt-3"><input className="form-control" readOnly value={invitationUrls[vacancy.id]} aria-label="Ссылка кандидата" /><button className="btn btn-outline-primary" onClick={() => copyLink(invitationUrls[vacancy.id])}>Копировать</button></div>}
            </div>
          </section>
        ))}
      </main>
    </>
  );
};

export default Homepage;
