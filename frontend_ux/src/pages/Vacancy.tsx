import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { User } from '../types';

const Vacancy: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';
  
  const [user, setUser] = useState<User | null>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [questions, setQuestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const userData = localStorage.getItem('user');
    if (!userData) {
      navigate('/login');
      return;
    }
    setUser(JSON.parse(userData));

    if (!isNew && id) {
      setLoading(true);
      api.get(`/vacancies/${id}`)
        .then(res => {
          const data = res.data;
          setTitle(data.title);
          setDescription(data.description);
          setQuestions(data.questions || []);
        })
        .catch(error => {
          alert('Ошибка загрузки вакансии');
        })
        .finally(() => setLoading(false));
    }
  }, [id, isNew, navigate]);

  const addQuestion = () => {
    setQuestions([...questions, '']);
  };

  const removeQuestion = (index: number) => {
    setQuestions(questions.filter((_, i) => i !== index));
  };

  const updateQuestion = (index: number, value: string) => {
    const updated = [...questions];
    updated[index] = value;
    setQuestions(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!title.trim()) {
      alert('Введите название вакансии');
      return;
    }

    const data = {
      title: title.trim(),
      description: description.trim(),
      questions: questions.filter(q => q.trim())
    };

    try {
      if (isNew) {
        await api.post('/vacancies', data);
      } else {
        await api.put(`/vacancies/${id}`, data);
      }
      navigate('/homepage');
    } catch (error) {
      alert('Ошибка сохранения вакансии');
    }
  };

  if (loading) {
    return (
      <div className="container text-center mt-5">
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Загрузка...</span>
        </div>
      </div>
    );
  }

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand">🤖 AI Интервьюер</span>
          <button 
            className="btn btn-sm btn-outline-secondary" 
            onClick={() => navigate('/homepage')}
          >
            ← На главную
          </button>
        </div>
      </nav>

      <div className="container mt-4" style={{ maxWidth: 700 }}>
        <div className="card">
          <div className="card-body">
            <form onSubmit={handleSubmit}>
              <div className="text-center mb-4">
                <h5>Название вакансии</h5>
                <input
                  className="form-control text-center"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Введите название вакансии"
                  required
                />
              </div>

              <div className="text-center mb-4">
                <h5>Описание вакансии</h5>
                <textarea
                  className="form-control text-center"
                  rows={3}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Введите описание вакансии"
                />
              </div>

              <div className="mb-3">
                <h5>Вопросы к вакансии</h5>
                
                {questions.length === 0 && (
                  <div className="text-muted text-center py-2">
                    Нет вопросов. Добавьте первый вопрос.
                  </div>
                )}
                
                {questions.map((q, i) => (
                  <div key={i} className="input-group mb-2">
                    <input
                      className="form-control"
                      value={q}
                      onChange={(e) => updateQuestion(i, e.target.value)}
                      placeholder={`Вопрос ${i + 1}`}
                    />
                    <button
                      type="button"
                      className="btn btn-outline-danger"
                      onClick={() => removeQuestion(i)}
                    >
                      ×
                    </button>
                  </div>
                ))}
                
                <button 
                  type="button" 
                  className="btn btn-outline-primary btn-sm"
                  onClick={addQuestion}
                >
                  ➕ Добавить вопрос
                </button>
              </div>

              <div className="text-end">
                <button type="submit" className="btn btn-primary px-5">
                  Сохранить
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </>
  );
};

export default Vacancy;