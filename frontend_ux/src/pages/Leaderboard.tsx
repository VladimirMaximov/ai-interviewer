import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';

const Leaderboard: React.FC = () => {
  const { vacancyId } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    const user = localStorage.getItem('user');
    if (!user) { navigate('/login'); return; }
    api.get(`/leaderboard/${vacancyId}`).then(res => setData(res.data || []));
  }, []);

  const downloadTranscript = (name: string) => {
    alert(`📄 Скачивание транскрипта для ${name}`);
  };

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand">🤖 AI Интервьюер</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => navigate('/homepage')}>
            ← Назад
          </button>
        </div>
      </nav>

      <div className="container mt-4" style={{ maxWidth: 950 }}>
        <div className="card">
          <div className="card-header bg-white text-center">
            <h5>🏆 Лидерборд</h5>
          </div>
          <div className="card-body p-0">
            <table className="table table-hover mb-0">
              <thead className="table-light">
                <tr>
                  <th>#</th>
                  <th>ФИО</th>
                  <th>Оценка ИИ</th>
                  <th>Оценка рекрутера</th>
                  <th>Оценка менеджера</th>
                  <th>Комментарий</th>
                  <th>Дата</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {data.map((item, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td><b>{item.name}</b></td>
                    <td><span className="badge bg-primary">{item.score}%</span></td>
                    <td>
                      <input 
                        type="number" 
                        className="form-control form-control-sm" 
                        style={{ width: 70 }}
                        defaultValue={item.recruiterScore || ''}
                        placeholder="—"
                        min="0"
                        max="100"
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        className="form-control form-control-sm" 
                        style={{ width: 70 }}
                        defaultValue={item.managerScore || ''}
                        placeholder="—"
                        min="0"
                        max="100"
                      />
                    </td>
                    <td>{item.comment || '—'}</td>
                    <td>{item.date || '—'}</td>
                    <td>
                      <button 
                        className="btn btn-sm btn-outline-primary"
                        onClick={() => downloadTranscript(item.name)}
                      >
                        📄
                      </button>
                    </td>
                  </tr>
                ))}
                {data.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center text-muted py-3">
                      Нет данных
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
};

export default Leaderboard;