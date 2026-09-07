import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getInterviewResult } from '../api';
import { InterviewResultDetail } from '../types';

function formatTimestamp(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(totalSeconds / 60)}:${(totalSeconds % 60).toString().padStart(2, '0')}`;
}

function assessmentSummary(assessment: Record<string, unknown> | null): string | null {
  const summary = assessment?.summary;
  if (!summary || typeof summary !== 'object') return null;
  const value = (summary as { summary?: unknown }).summary;
  return typeof value === 'string' ? value : null;
}

type QuestionAssessment = { response_id?: string; score?: number | null; observations?: Array<{ criterion_id?: string; label?: string; confidence?: number; explanation?: string }> };

function questionAssessments(assessment: Record<string, unknown> | null): QuestionAssessment[] {
  const value = assessment?.question_assessments;
  return Array.isArray(value) ? value as QuestionAssessment[] : [];
}

const labelNames: Record<string, string> = {
  contradicted: 'Не подтверждено', weak: 'Слабый ответ', neutral: 'Частично подтверждено',
  supported: 'Подтверждено', strong: 'Сильный ответ', insufficient_information: 'Недостаточно данных',
};

const eventNames: Record<string, string> = {
  face_missing: 'Лицо отсутствовало в кадре', multiple_faces: 'В кадре несколько лиц',
  face_detection_unavailable: 'Детектор лица был недоступен', page_hidden: 'Открыта другая вкладка',
  page_visible: 'Возврат на вкладку интервью', window_blurred: 'Окно интервью потеряло фокус',
  window_focused: 'Фокус возвращён в окно интервью', page_copy: 'Копирование текста',
};

const CandidateDetails: React.FC = () => {
  const { vacancyId = '', candidateId = '' } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState<InterviewResultDetail | null>(null);
  const [error, setError] = useState('');
  const [selectedMediaIndex, setSelectedMediaIndex] = useState(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pendingSeekSeconds = useRef<number | null>(null);

  useEffect(() => {
    let active = true;
    let loaded = false;
    const load = () => getInterviewResult(vacancyId, candidateId)
      .then((value) => {
        if (active) {
          loaded = true;
          setResult(value);
          setError('');
        }
      })
      .catch(() => {
        if (active && !loaded) setError('Не удалось загрузить сохранённые результаты интервью.');
      });
    load();
    const interval = window.setInterval(load, 5000);
    return () => { active = false; window.clearInterval(interval); };
  }, [vacancyId, candidateId]);

  const playFrom = (offsetMs: number) => {
    if (!result?.media.length) return;
    const foundIndex = result.media.findIndex(
      (item) => offsetMs >= item.start_offset_ms && offsetMs < item.end_offset_ms,
    );
    const mediaIndex = foundIndex >= 0 ? foundIndex : 0;
    const seekSeconds = Math.max(0, (offsetMs - result.media[mediaIndex].start_offset_ms) / 1000);
    pendingSeekSeconds.current = seekSeconds;
    if (mediaIndex !== selectedMediaIndex) {
      setSelectedMediaIndex(mediaIndex);
    } else if (videoRef.current) {
      videoRef.current.currentTime = seekSeconds;
      pendingSeekSeconds.current = null;
      void videoRef.current.play();
    }
  };

  const applyPendingSeek = () => {
    if (videoRef.current && pendingSeekSeconds.current !== null) {
      videoRef.current.currentTime = pendingSeekSeconds.current;
      pendingSeekSeconds.current = null;
      void videoRef.current.play();
    }
  };

  const selectedMedia = result?.media[selectedMediaIndex] ?? result?.media[0];
  const generatedSummary = result ? assessmentSummary(result.assessment) : null;
  const feedback = result?.assessment?.summary as undefined | { headline?: string; strengths?: Array<{ title: string; detail: string }>; growth_areas?: Array<{ title: string; detail: string; action?: string }>; next_steps?: string[]; limitations?: string[] };
  const assessments = result ? questionAssessments(result.assessment) : [];

  return <>
    <nav className="navbar navbar-light bg-white shadow-sm"><div className="container"><span className="navbar-brand">AI Интервьюер</span><button className="btn btn-sm btn-outline-secondary" onClick={() => navigate(`/leaderboard/${vacancyId}`)}>← К интервью</button></div></nav>
    <main className="container my-4" style={{ maxWidth: 1180 }}>
      {error && <div className="alert alert-danger">{error}</div>}{!result && !error && <p className="text-muted">Загружаем материалы…</p>}
      {result && <><section className="card shadow-sm mb-4"><div className="card-body"><div className="d-flex flex-wrap justify-content-between gap-3"><div><small className="text-muted">Кандидат</small><h4>{result.summary.candidate_alias || 'Кандидат без имени'}</h4></div><div><small className="text-muted">Вакансия</small><h5>{result.vacancy_title}</h5></div><div><small className="text-muted">Оценка</small><h5>{result.summary.score === null ? 'Не рассчитана' : `${result.summary.score} / 10`}</h5></div></div>{generatedSummary && <div className="border-top mt-3 pt-3"><h6>{feedback?.headline || 'Итоговый отчёт ИИ'}</h6><p>{generatedSummary}</p>{feedback?.strengths?.length ? <><strong>Сильные стороны</strong><ul>{feedback.strengths.map((item) => <li key={item.title}>{item.title}: {item.detail}</li>)}</ul></> : null}{feedback?.growth_areas?.length ? <><strong>Зоны развития</strong><ul>{feedback.growth_areas.map((item) => <li key={item.title}>{item.title}: {item.detail}{item.action ? ` Рекомендация: ${item.action}` : ''}</li>)}</ul></> : null}{feedback?.next_steps?.length ? <><strong>Следующие шаги</strong><ul>{feedback.next_steps.map((item) => <li key={item}>{item}</li>)}</ul></> : null}{feedback?.limitations?.length ? <p className="small text-muted mb-0">Ограничения анализа: {feedback.limitations.join('; ')}</p> : null}</div>}{result.assessment && !generatedSummary && <p className="text-muted border-top mt-3 pt-3 mb-0">Итоговый отчёт ещё формируется. Оценки готовых ответов показаны ниже.</p>}</div></section><div className="row g-4">
        <div className="col-lg-5"><section className="card shadow-sm h-100"><div className="card-body"><h5>Запись интервью</h5><p className="text-muted">{result.recording_duration_ms ? `${Math.round(result.recording_duration_ms / 1000)} с` : 'Длительность уточняется'}{result.media.length === 1 ? ' · цельная запись' : result.media.length > 1 ? ` · ${result.media.length} фрагментов` : ''}</p>{selectedMedia ? <video ref={videoRef} className="w-100 rounded mb-2 bg-dark" controls preload="metadata" src={selectedMedia.url} onLoadedMetadata={applyPendingSeek} /> : <div className="alert alert-light">Подтверждённых видеофрагментов пока нет.</div>}<h6 className="mt-4">События проверки</h6>{result.monitoring_events.length ? result.monitoring_events.map((event) => <div className="small border rounded p-2 mb-2" key={event.id}><button type="button" className="btn btn-link btn-sm p-0" onClick={() => playFrom(event.started_at_ms)}>{formatTimestamp(event.started_at_ms)}–{formatTimestamp(event.ended_at_ms)}</button> · {eventNames[event.kind] || event.kind} · {event.review_status}{event.evidence_url && <> · <a href={event.evidence_url}>фрагмент</a></>}</div>) : <p className="text-muted small">Событий камеры с точными интервалами не зафиксировано.</p>}<h6 className="mt-4">Активность браузера</h6>{result.timeline_events.length ? result.timeline_events.map((event) => <div className="small border rounded p-2 mb-2" key={event.id}><button type="button" className="btn btn-link btn-sm p-0" onClick={() => playFrom(event.recording_offset_ms)}>{formatTimestamp(event.recording_offset_ms)}</button> · {eventNames[event.event_type] || event.event_type}</div>) : <p className="text-muted small">Переключений вкладок, потери фокуса и копирования не зафиксировано.</p>}</div></section></div>
        <div className="col-lg-7"><section className="card shadow-sm h-100"><div className="card-body"><h5>Ответы и расшифровка</h5>{result.answers.length ? result.answers.map((answer, index) => { const answerAssessment = assessments.find((item) => item.response_id === answer.response_id); return <article className="border-bottom py-3" key={answer.response_id}><small className="text-muted">Вопрос {index + 1}{answer.is_follow_up ? ' · уточнение' : ''} · </small>{answer.start_offset_ms === null ? <small className="text-muted">нет временной отметки</small> : <button type="button" className="btn btn-link btn-sm p-0 align-baseline" onClick={() => playFrom(answer.start_offset_ms!)} aria-label={`Перейти к ответу на отметке ${formatTimestamp(answer.start_offset_ms)}`}>{formatTimestamp(answer.start_offset_ms)}–{formatTimestamp(answer.end_offset_ms ?? answer.start_offset_ms)}</button>}<h6 className="mt-1">{answer.question_text}</h6>{answer.transcription_status === 'completed' ? <p>{answer.transcript_text || 'Речь не обнаружена.'}</p> : <p className={answer.transcription_status === 'failed' ? 'text-danger' : 'text-muted'}>Расшифровка: {answer.transcription_status}</p>}{answer.timed_out && <span className="badge bg-warning text-dark mb-2">Завершено по таймеру</span>}{answer.code && <><div className="small text-muted">Код · {answer.code.language}</div><pre className="bg-dark text-light rounded p-3 overflow-auto"><code>{answer.code.source_code}</code></pre></>}{answerAssessment ? <div className="bg-light rounded p-3 mt-2"><strong>Оценка ответа: {answerAssessment.score === null || answerAssessment.score === undefined ? 'недостаточно данных' : `${answerAssessment.score} / 10`}</strong>{answerAssessment.observations?.map((observation) => <div className="small mt-2" key={`${observation.criterion_id}-${observation.label}`}><span className="badge bg-secondary me-2">{labelNames[observation.label || ''] || observation.label}</span>{observation.explanation}{observation.confidence !== undefined ? ` · уверенность ${Math.round(observation.confidence * 100)}%` : ''}</div>)}</div> : <p className="small text-muted mt-2">Оценка этого ответа ещё формируется.</p>}</article>; }) : <p className="text-muted">Ответов пока нет.</p>}</div></section></div>
      </div></>}
    </main>
  </>;
};

export default CandidateDetails;
