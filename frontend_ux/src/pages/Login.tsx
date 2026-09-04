import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';

const Login: React.FC = () => {
  const [username, setUsername] = useState('candidate');
  const [password, setPassword] = useState('1234');
  const [isRegister, setIsRegister] = useState(false);
  const [role, setRole] = useState('candidate');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    try {
      const response = await api.post('/login', { username, password });
      if (response.data.user) {
        localStorage.setItem('user', JSON.stringify(response.data.user));
        navigate('/homepage');
      }
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Ошибка входа');
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    try {
      await api.post('/register', { username, password, role });
      alert('Регистрация успешна! Теперь войдите.');
      setIsRegister(false);
    } catch (error: any) {
      setError(error.response?.data?.detail || 'Ошибка регистрации');
    }
  };

  return (
    <div className="container" style={{ maxWidth: 400, marginTop: 80 }}>
      <div className="card p-4 shadow">
        <h3 className="text-center">🤖 AI Интервьюер</h3>
        
        {error && <div className="alert alert-danger">{error}</div>}
        
        <form onSubmit={isRegister ? handleRegister : handleLogin}>
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
          
          {isRegister && (
            <select 
              className="form-select mb-2"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            >
              <option value="candidate">Кандидат</option>
              <option value="interviewer">Интервьюер</option>
              <option value="hiring_manager">Нанимающий менеджер</option>
            </select>
          )}
          
          <button type="submit" className="btn btn-primary w-100">
            {isRegister ? 'Зарегистрироваться' : 'Войти'}
          </button>
        </form>
        
        <div className="text-center mt-2">
          <button 
            className="btn btn-link btn-sm"
            onClick={() => setIsRegister(!isRegister)}
          >
            {isRegister ? 'Уже есть аккаунт?' : 'Нет аккаунта?'}
          </button>
          <div className="text-muted small mt-1">
            <span className="badge bg-secondary me-1">candidate</span>
            <span className="badge bg-secondary me-1">interviewer</span>
            <span className="badge bg-secondary">manager</span>
            <div>Пароль: 1234</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;