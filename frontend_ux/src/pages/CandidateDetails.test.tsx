import React, { act } from 'react';
import { createRoot, Root } from 'react-dom/client';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import CandidateDetails from './CandidateDetails';
import { getInterviewResult } from '../api';

jest.mock('../api', () => ({ getInterviewResult: jest.fn() }));
const getResult = getInterviewResult as jest.MockedFunction<typeof getInterviewResult>;

describe('real candidate result states', () => {
  let node: HTMLDivElement; let root: Root;
  beforeEach(() => { (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true; node = document.createElement('div'); document.body.appendChild(node); root = createRoot(node); });
  afterEach(() => { act(() => root.unmount()); node.remove(); jest.clearAllMocks(); });
  const render = async () => { await act(async () => { root.render(<MemoryRouter initialEntries={['/leaderboard/v/candidate/s']}><Routes><Route path="/leaderboard/:vacancyId/candidate/:candidateId" element={<CandidateDetails />} /></Routes></MemoryRouter>); await Promise.resolve(); }); };

  test('shows spoken, coding, follow-up, pending and failed evidence explicitly', async () => {
    getResult.mockResolvedValue({ summary: { session_id: 's', invitation_id: 'i', candidate_alias: 'Test', status: 'processing', score: null, answered_questions: 3, total_questions: 2, expires_at: '', submitted_at: '' }, vacancy_title: 'Backend', recording_duration_ms: 12000, media: [], monitoring_events: [], timeline_events: [], assessment: null, answers: [
      { response_id: '1', question_id: 'q1', question_text: 'Основной', question_kind: 'spoken', is_follow_up: false, transcription_status: 'pending', transcript_text: null, start_offset_ms: 0, end_offset_ms: 3000, timed_out: false, code: null },
      { response_id: '2', question_id: 'q2', question_text: 'Код', question_kind: 'coding', is_follow_up: false, transcription_status: 'failed', transcript_text: null, start_offset_ms: 3000, end_offset_ms: 7000, timed_out: true, code: { language: 'python', source_code: 'return 42' } },
      { response_id: '3', question_id: 'q3', question_text: 'Уточните', question_kind: 'spoken', is_follow_up: true, transcription_status: 'completed', transcript_text: 'Подробный ответ', start_offset_ms: 7000, end_offset_ms: 12000, timed_out: false, code: null },
    ] });
    await render();
    expect(node.textContent).toContain('Расшифровка: pending'); expect(node.textContent).toContain('Расшифровка: failed'); expect(node.textContent).toContain('return 42'); expect(node.textContent).toContain('уточнение'); expect(node.textContent).toContain('Подробный ответ'); expect(node.textContent).toContain('Не рассчитана');
  });

  test('shows an explicit empty result', async () => {
    getResult.mockResolvedValue({ summary: { session_id: 's', invitation_id: 'i', candidate_alias: null, status: 'in_progress', score: null, answered_questions: 0, total_questions: 3, expires_at: '', submitted_at: null }, vacancy_title: 'Backend', recording_duration_ms: null, media: [], answers: [], monitoring_events: [], timeline_events: [], assessment: null });
    await render(); expect(node.textContent).toContain('Ответов пока нет'); expect(node.textContent).toContain('Подтверждённых видеофрагментов пока нет');
  });

  test('shows AI summary, per-question score and clickable monitoring timing', async () => {
    getResult.mockResolvedValue({ summary: { session_id: 's', invitation_id: 'i', candidate_alias: 'Test', status: 'completed', score: 8, answered_questions: 1, total_questions: 1, expires_at: '', submitted_at: '' }, vacancy_title: 'ML', recording_duration_ms: 10000, media: [{ sequence: 0, start_offset_ms: 0, end_offset_ms: 10000, content_type: 'video/webm', url: '/video' }], monitoring_events: [{ id: 'e', response_id: '1', question_id: 'q1', kind: 'face_missing', started_at_ms: 3000, ended_at_ms: 5000, review_status: 'pending', evidence_url: null }], timeline_events: [{ id: 't', question_id: 'q1', event_type: 'window_blurred', recording_offset_ms: 4000 }], assessment: { summary: { headline: 'Итог', summary: 'Суммаризированный отчёт', strengths: [], growth_areas: [], next_steps: ['Практиковать Python'], limitations: ['Без резюме'] }, question_assessments: [{ response_id: '1', score: 7.5, observations: [{ criterion_id: 'python', label: 'supported', confidence: 0.8, explanation: 'Приведён корректный пример.' }] }] }, answers: [
      { response_id: '1', question_id: 'q1', question_text: 'Вопрос', question_kind: 'spoken', is_follow_up: false, transcription_status: 'completed', transcript_text: 'Ответ', start_offset_ms: 3000, end_offset_ms: 5000, timed_out: false, code: null },
    ] });
    await render();
    expect(node.textContent).toContain('Суммаризированный отчёт');
    expect(node.textContent).toContain('Оценка ответа: 7.5 / 10');
    expect(node.textContent).toContain('Приведён корректный пример');
    expect(node.textContent).toContain('0:03–0:05');
  });
});
