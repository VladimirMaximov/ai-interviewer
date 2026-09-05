import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

const Login: React.FC = () => {
  const [username, setUsername] = useState('interviewer');
  const [password, setPassword] = useState('1234');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    try {
      // Отправляем JSON вместо FormData
      const response = await api.post('/login', {
        username,
        password
      });

      if (response.data) {
        localStorage.setItem('user', JSON.stringify(response.data));
        navigate('/homepage');
      }
    } catch (error: any) {
      console.error('Ошибка:', error);
      if (!error.response) {
        setError('Нет соединения с сервером. Запустите backend на порту 8000.');
      } else {
        setError(error.response.data?.detail || 'Не удалось войти. Проверьте логин и пароль.');
      }
    }
  };

  return (
    <div className="container" style={{ maxWidth: 400, marginTop: 80 }}>
      <div className="card p-4 shadow">
        <h3 className="text-center">AI Интервьюер</h3>
        
        {error && <div className="alert alert-danger">{error}</div>}
        
        <form onSubmit={handleLogin}>
          <input
            className="form-control mb-2"
            placeholder="Логин"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
          <input
            type="password"
            className="form-control mb-2"
            placeholder="Пароль"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          
          <button type="submit" className="btn btn-primary w-100">
            Войти
          </button>
        </form>
        
        <div className="text-center mt-2">
          <small className="text-muted">
            interviewer / 1234 &nbsp;|&nbsp; candidate / 1234 &nbsp;|&nbsp; manager / 1234
          </small>
        </div>
      </div>
    </div>
  );
};

export default Login;
