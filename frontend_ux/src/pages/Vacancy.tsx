import React, { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';

const Vacancy: React.FC = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isNew = id === 'new';
  
  const [user, setUser] = useState<any>(null);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [questions, setQuestions] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    const data = localStorage.getItem('user');
    if (!data) { navigate('/login'); return; }
    setUser(JSON.parse(data));

    if (!isNew && id) {
      api.get(`/vacancies/${id}`).then(res => {
        const data = res.data;
        setTitle(data.title || '');
        setDescription(data.description || '');
        setQuestions(data.questions?.map((q: any) => q.question_text || q.text || q) || []);
      });
    }
  }, []);

  const addQuestion = () => setQuestions([...questions, '']);
  const removeQuestion = (index: number) => setQuestions(questions.filter((_, i) => i !== index));
  const updateQuestion = (index: number, value: string) => {
    const updated = [...questions];
    updated[index] = value;
    setQuestions(updated);
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setSaveError('');
    
    if (!title.trim()) {
      setSaveError('Введите название вакансии');
      return;
    }

    const data = {
      title: title.trim(),
      description: description.trim(),
      recruiter_id: user?.id || '1',
      manager_id: '3',
      questions: questions.filter(q => q.trim())
    };

    console.log('Отправка:', data);

    try {
      setSaving(true);
      if (isNew) {
        const response = await api.post('/vacancies', data);
        if (!response.data?.id) throw new Error('Backend did not return a vacancy id');
        navigate('/homepage', {
          replace: true,
          state: {
            createdVacancy: {
              ...data,
              ...response.data
            }
          }
        });
        return;
      } else if (id) {
        await api.put(`/vacancies/${id}`, data);
      }
      navigate('/homepage');
    } catch (error: any) {
      console.error('Ошибка:', error);
      setSaveError(error.response?.data?.detail || 'Не удалось сохранить вакансию. Проверьте, что backend запущен на порту 8000.');
    } finally {
      setSaving(false);
    }
  };

  if (!user) return null;

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand">AI Интервьюер</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => navigate('/homepage')}>
            ← На главную
          </button>
        </div>
      </nav>

      <div className="container mt-4" style={{ maxWidth: 700 }}>
        <div className="card">
          <div className="card-body">
            <form onSubmit={handleSubmit}>
              {saveError && <div className="alert alert-danger">{saveError}</div>}
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
                <button type="button" className="btn btn-outline-primary btn-sm" onClick={addQuestion}>
                  Добавить вопрос
                </button>
              </div>

              <div className="text-end">
                <button
                  type="button"
                  className="btn btn-primary px-5"
                  disabled={saving}
                  onClick={() => handleSubmit()}
                >
                  {saving ? 'Сохраняем…' : 'Сохранить'}
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
