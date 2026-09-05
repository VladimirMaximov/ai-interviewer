import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

const CandidateHome: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const data = localStorage.getItem('user');
    if (!data) { navigate('/login'); return; }
    setUser(JSON.parse(data));
  }, []);

  const copyLink = () => {
    const link = `https://your-interview-service.com/interview/${user?.id}`;
    navigator.clipboard.writeText(link);
    alert('Ссылка скопирована!');
  };

  if (!user) return null;

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand">AI Интервьюер</span>
          <button className="btn btn-sm btn-outline-danger" onClick={() => {
            localStorage.clear();
            navigate('/login');
          }}>Выйти</button>
        </div>
      </nav>

      <div className="container mt-5" style={{ maxWidth: 600 }}>
        <div className="card">
          <div className="card-body text-center">
            <h4 className="mb-4">Ваша ссылка для интервью</h4>
            <div className="p-3 bg-light rounded">
              <code className="text-break">
                https://your-interview-service.com/interview/{user.id}
              </code>
            </div>
            <button className="btn btn-primary mt-3" onClick={copyLink}>
              Скопировать ссылку
            </button>
            <p className="text-muted mt-3">
              Перейдите по ссылке, чтобы начать интервью
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default CandidateHome;
