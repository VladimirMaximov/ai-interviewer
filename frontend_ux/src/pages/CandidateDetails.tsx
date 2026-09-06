import React, { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getInterviewResult } from '../api';
import { InterviewResultDetail } from '../types';

function formatTimestamp(milliseconds: number): string {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  return `${Math.floor(totalSeconds / 60)}:${(totalSeconds % 60).toString().padStart(2, '0')}`;
}

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

  return <>
    <nav className="navbar navbar-light bg-white shadow-sm"><div className="container"><span className="navbar-brand">AI Интервьюер</span><button className="btn btn-sm btn-outline-secondary" onClick={() => navigate(`/leaderboard/${vacancyId}`)}>← К интервью</button></div></nav>
    <main className="container my-4" style={{ maxWidth: 1180 }}>
      {error && <div className="alert alert-danger">{error}</div>}{!result && !error && <p className="text-muted">Загружаем материалы…</p>}
      {result && <><section className="card shadow-sm mb-4"><div className="card-body d-flex flex-wrap justify-content-between gap-3"><div><small className="text-muted">Кандидат</small><h4>{result.summary.candidate_alias || 'Кандидат без имени'}</h4></div><div><small className="text-muted">Вакансия</small><h5>{result.vacancy_title}</h5></div><div><small className="text-muted">Оценка</small><h5>{result.summary.score === null ? 'Не рассчитана' : `${result.summary.score}%`}</h5></div></div></section><div className="row g-4">
        <div className="col-lg-5"><section className="card shadow-sm h-100"><div className="card-body"><h5>Запись интервью</h5><p className="text-muted">{result.recording_duration_ms ? `${Math.round(result.recording_duration_ms / 1000)} с` : 'Длительность уточняется'}{result.media.length === 1 ? ' · цельная запись' : result.media.length > 1 ? ` · ${result.media.length} фрагментов` : ''}</p>{selectedMedia ? <video ref={videoRef} className="w-100 rounded mb-2 bg-dark" controls preload="metadata" src={selectedMedia.url} onLoadedMetadata={applyPendingSeek} /> : <div className="alert alert-light">Подтверждённых видеофрагментов пока нет.</div>}<h6 className="mt-4">События проверки</h6>{result.monitoring_events.length ? result.monitoring_events.map((event) => <div className="small border rounded p-2 mb-2" key={event.id}>{event.kind}: {event.started_at_ms / 1000}–{event.ended_at_ms / 1000} с · {event.review_status}{event.evidence_url && <> · <a href={event.evidence_url}>фрагмент</a></>}</div>) : <p className="text-muted small">Событий нет.</p>}</div></section></div>
        <div className="col-lg-7"><section className="card shadow-sm h-100"><div className="card-body"><h5>Ответы и расшифровка</h5>{result.answers.length ? result.answers.map((answer, index) => <article className="border-bottom py-3" key={answer.response_id}><small className="text-muted">Вопрос {index + 1}{answer.is_follow_up ? ' · уточнение' : ''} · </small>{answer.start_offset_ms === null ? <small className="text-muted">нет временной отметки</small> : <button type="button" className="btn btn-link btn-sm p-0 align-baseline" onClick={() => playFrom(answer.start_offset_ms!)} aria-label={`Перейти к ответу на отметке ${formatTimestamp(answer.start_offset_ms)}`}>{formatTimestamp(answer.start_offset_ms)}–{formatTimestamp(answer.end_offset_ms ?? answer.start_offset_ms)}</button>}<h6 className="mt-1">{answer.question_text}</h6>{answer.transcription_status === 'completed' ? <p>{answer.transcript_text || 'Речь не обнаружена.'}</p> : <p className={answer.transcription_status === 'failed' ? 'text-danger' : 'text-muted'}>Расшифровка: {answer.transcription_status}</p>}{answer.timed_out && <span className="badge bg-warning text-dark mb-2">Завершено по таймеру</span>}{answer.code && <><div className="small text-muted">Код · {answer.code.language}</div><pre className="bg-dark text-light rounded p-3 overflow-auto"><code>{answer.code.source_code}</code></pre></>}</article>) : <p className="text-muted">Ответов пока нет.</p>}</div></section></div>
      </div></>}
    </main>
  </>;
};

export default CandidateDetails;
