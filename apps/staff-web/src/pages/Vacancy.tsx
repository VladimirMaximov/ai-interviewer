import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  createDefaultConfiguration,
  createVacancy,
  getConfiguration,
  getVacancy,
  newQuestion,
  saveConfiguration,
} from '../api';
import { ConfiguredQuestion, InterviewConfiguration } from '../types';

const Vacancy: React.FC = () => {
  const { id } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  // The explicit `/vacancy/new` route has no `:id` param.
  const isNew = id === 'new' || location.pathname.endsWith('/vacancy/new');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [managerWishes, setManagerWishes] = useState('');
  const [configuration, setConfiguration] = useState<InterviewConfiguration>(
    createDefaultConfiguration,
  );
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    if (isNew || !id) return;
    Promise.all([getVacancy(id), getConfiguration(id)])
      .then(([vacancy, value]) => {
        setTitle(vacancy.title);
        setDescription(vacancy.description);
        setManagerWishes(vacancy.manager_wishes || 'Пожелания нанимающего менеджера пока не добавлены.');
        setConfiguration(value);
      })
      .catch(() => setSaveError('Не удалось загрузить конфигурацию вакансии.'));
  }, [id, isNew]);

  const changeQuestions = (
    blockIndex: number,
    updater: (current: ConfiguredQuestion[]) => ConfiguredQuestion[],
  ) => setConfiguration((current) => ({
    ...current,
    blocks: current.blocks.map((block, index) => index === blockIndex
      ? { ...block, questions: updater(block.questions) }
      : block),
  }));

  const updateQuestion = (
    blockIndex: number,
    questionIndex: number,
    patch: Partial<ConfiguredQuestion>,
  ) => changeQuestions(blockIndex, (questions) => questions.map((question, index) => {
    if (index !== questionIndex) return question;
    const next = { ...question, ...patch };
    if (patch.kind === 'spoken') delete next.language;
    if (patch.kind === 'coding') next.language = next.language || 'python';
    return next;
  }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaveError('');
    if (!title.trim()) return setSaveError('Введите название вакансии.');
    if (!configuration.blocks.some((block) => block.questions.some((q) => q.text.trim()))) {
      return setSaveError('Добавьте хотя бы один вопрос.');
    }
    const cleaned = {
      ...configuration,
      live_coding_enabled: configuration.blocks.some((block) =>
        block.questions.some((question) => question.kind === 'coding')),
      blocks: configuration.blocks.map((block) => ({
        ...block,
        questions: block.questions
          .filter((question) => question.text.trim())
          .map((question) => ({ ...question, text: question.text.trim() })),
      })),
    };
    try {
      setSaving(true);
      const vacancy = isNew
        ? await createVacancy(title.trim(), description.trim())
        : await getVacancy(id!);
      await saveConfiguration(vacancy.id, cleaned);
      navigate('/homepage', { replace: true, state: { createdVacancy: vacancy } });
    } catch (error: any) {
      setSaveError(error.response?.data?.error?.message
        || 'Не удалось сохранить вакансию и вопросы.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <nav className="navbar navbar-light bg-white shadow-sm">
        <div className="container">
          <span className="navbar-brand">AI Интервьюер</span>
          <button className="btn btn-sm btn-outline-secondary" onClick={() => navigate('/homepage')}>← На главную</button>
        </div>
      </nav>
      <main className="container my-4" style={{ maxWidth: 920 }}>
        <form className="card shadow-sm" onSubmit={submit}>
          <div className="card-body p-4">
            <h2 className="h4 mb-4">{isNew ? 'Настройка интервью' : 'Просмотр вакансии'}</h2>
            {!isNew && <div className="alert alert-info">Демонстрационный режим: поля вакансии и вопросы доступны только для просмотра.</div>}
            {saveError && <div className="alert alert-danger">{saveError}</div>}
            <label className="form-label">Название вакансии</label>
            <input className="form-control mb-3" value={title} onChange={(e) => setTitle(e.target.value)} required disabled={!isNew} />
            <label className="form-label">Описание вакансии</label>
            <textarea className="form-control mb-4" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} disabled={!isNew} />
            {!isNew && <><label className="form-label">Пожелания нанимающего менеджера</label><textarea className="form-control mb-4" rows={5} value={managerWishes} disabled /></>}

            {configuration.blocks.map((block, blockIndex) => (
              <section className="border rounded-3 p-3 mb-3" key={block.id}>
                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div><small className="text-muted">Блок {blockIndex + 1}</small><h3 className="h5 mb-0">{block.title}</h3></div>
                  {isNew && <button type="button" className="btn btn-sm btn-outline-primary" onClick={() => changeQuestions(blockIndex, (items) => [...items, newQuestion()])}>Добавить вопрос</button>}
                </div>
                {block.questions.map((question, questionIndex) => (
                  <div className="bg-light rounded-3 p-3 mb-2" key={question.id}>
                    <textarea className="form-control mb-2" rows={2} value={question.text} onChange={(e) => updateQuestion(blockIndex, questionIndex, { text: e.target.value })} placeholder={`Вопрос ${questionIndex + 1}`} disabled={!isNew} />
                    <div className="row g-2 align-items-center">
                      <div className="col-md-3"><select className="form-select" value={question.kind} onChange={(e) => updateQuestion(blockIndex, questionIndex, { kind: e.target.value as 'spoken' | 'coding' })} disabled={!isNew || block.key !== 'hard_skills'}><option value="spoken">Устный ответ</option>{block.key === 'hard_skills' && <option value="coding">Live coding + голос</option>}</select></div>
                      <div className="col-md-3"><input className="form-control" type="number" min="1" max="120" placeholder="Лимит, минут" value={question.time_limit_seconds ? question.time_limit_seconds / 60 : ''} onChange={(e) => updateQuestion(blockIndex, questionIndex, { time_limit_seconds: e.target.value ? Number(e.target.value) * 60 : null })} disabled={!isNew} /></div>
                      <div className="col-md-4 form-check ms-2"><input className="form-check-input" type="checkbox" checked={question.follow_up_after_answer} onChange={(e) => updateQuestion(blockIndex, questionIndex, { follow_up_after_answer: e.target.checked })} disabled={!isNew} /><label className="form-check-label">Разрешить уточнения</label></div>
                      {isNew && <div className="col text-end"><button type="button" className="btn btn-sm btn-outline-danger" aria-label="Удалить вопрос" onClick={() => changeQuestions(blockIndex, (items) => items.filter((_, index) => index !== questionIndex))}>×</button></div>}
                    </div>
                  </div>
                ))}
              </section>
            ))}
            {isNew && <div className="text-end"><button className="btn btn-primary px-5" disabled={saving}>{saving ? 'Сохраняем…' : 'Сохранить'}</button></div>}
          </div>
        </form>
      </main>
    </>
  );
};

export default Vacancy;
