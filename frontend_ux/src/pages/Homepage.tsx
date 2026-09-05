import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import api from '../api';

const Homepage: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [vacancies, setVacancies] = useState<any[]>([]);
  const [loadError, setLoadError] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const createdVacancy = location.state?.createdVacancy;

  useEffect(() => {
    const data = localStorage.getItem('user');
    if (!data) { navigate('/login'); return; }
    setUser(JSON.parse(data));
    if (createdVacancy) setVacancies([createdVacancy]);
    api.get('/vacancies')
      .then(res => {
        const loadedVacancies = res.data || [];
        setVacancies(current => {
          if (!createdVacancy) return loadedVacancies;
          const withoutDuplicate = loadedVacancies.filter(
            (vacancy: any) => vacancy.id !== createdVacancy.id
          );
          return [createdVacancy, ...withoutDuplicate];
        });
        setLoadError('');
      })
      .catch(() => {
        setLoadError('Не удалось обновить список вакансий. Только что созданная вакансия показана ниже.');
      });
  }, [createdVacancy, navigate]);

  const logout = () => {
    localStorage.clear();
    navigate('/login');
  };

  const copyLink = (link: string) => {
    navigator.clipboard.writeText(link);
    alert('Ссылка скопирована!');
  };

  if (!user) return null;

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand">AI Интервьюер</span>
          <div>
            <span className="badge bg-secondary me-2">{user.role}</span>
            <button className="btn btn-sm btn-outline-danger" onClick={logout}>Выйти</button>
          </div>
        </div>
      </nav>

      <div className="container mt-4">
        {user.role === 'candidate' ? (
          // Для кандидата - показываем персональную ссылку
          <div className="card">
            <div className="card-body text-center">
              <h5>Ваша персональная ссылка для интервью</h5>
              <div className="mt-3 p-3 bg-light rounded">
                <code className="text-break">
                  https://your-interview-service.com/interview/{user.id}
                </code>
              </div>
              <button 
                className="btn btn-primary mt-3"
                onClick={() => copyLink(`https://your-interview-service.com/interview/${user.id}`)}
              >
                Скопировать ссылку
              </button>
              <p className="text-muted mt-3 small">
                Перейдите по ссылке, чтобы начать интервью
              </p>
            </div>
          </div>
        ) : (
          // Для интервьюера - список вакансий
          <>
            {createdVacancy && (
              <div className="alert alert-success" role="status">
                Вакансия «{createdVacancy.title}» сохранена и добавлена в список.
              </div>
            )}
            <h5 className="mb-3">Список вакансий</h5>
            {loadError && <div className="alert alert-warning">{loadError}</div>}
            {vacancies.map((v: any) => (
              <div key={v.id} className="card mb-2 p-3">
                <b>{v.title}</b>
                <small className="text-muted d-block">{v.description}</small>
                <Link to={`/leaderboard/${v.id}`} className="btn btn-sm btn-outline-primary mt-2">
                  Лидерборд
                </Link>
              </div>
            ))}
            <Link to="/vacancy/new" className="btn btn-outline-primary w-100 py-2">
              Новая вакансия
            </Link>
          </>
        )}
      </div>
    </>
  );
};

export default Homepage;
