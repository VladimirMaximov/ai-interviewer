import React, { useState } from 'react';

type Status = '' | 'ok' | 'not_ok';
const labels: Record<Status, string> = { '': '', ok: 'ОК', not_ok: 'Отказ' };

const RecruiterStatus: React.FC<{ vacancyId?: string; candidateId: string }> = ({ vacancyId, candidateId }) => {
  const key = `recruiter-status:${vacancyId}:${candidateId}`;
  const [status, setStatus] = useState<Status>(() => {
    const saved = localStorage.getItem(key);
    return saved === 'ok' || saved === 'not_ok' ? saved : '';
  });
  const [error, setError] = useState('');
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const canEdit = user.role === 'interviewer' || user.role === 'recruiter';
  const color = status === 'ok' ? 'success' : status === 'not_ok' ? 'danger' : 'secondary';

  if (!canEdit) return <span className={`badge bg-${color}`}>{labels[status]}</span>;

  return (
    <div onClick={(event) => event.stopPropagation()}>
      <select
        aria-label="Решение рекрутера"
        className={`form-select form-select-sm text-${color}`}
        style={{ minWidth: 145 }}
        value={status}
        onChange={(event) => {
          const next = event.target.value as Status;
          try {
            localStorage.setItem(key, next);
            setStatus(next);
            setError('');
          } catch {
            setError('Не удалось сохранить. Попробуйте ещё раз.');
          }
        }}
      >
        <option value="" aria-label="Без решения"></option>
        <option value="ok">ОК</option>
        <option value="not_ok">Отказ</option>
      </select>
      {error && <small className="text-danger" role="alert">{error}</small>}
    </div>
  );
};

export default RecruiterStatus;
