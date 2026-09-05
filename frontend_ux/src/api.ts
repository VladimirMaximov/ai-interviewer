import axios from 'axios';
import {
  ConfiguredQuestion,
  InterviewConfiguration,
  InvitationCreated,
  QuestionBlockKey,
  Vacancy,
  InterviewResultDetail,
  InterviewResultSummary,
} from './types';

const API_URL = process.env.REACT_APP_API_URL
  || (process.env.NODE_ENV === 'development' ? 'http://127.0.0.1:8000' : '/api');
const recruiterKey = process.env.REACT_APP_RECRUITER_KEY || 'local-recruiter-key';
const recruiterId = process.env.REACT_APP_RECRUITER_ID || 'recruiter-demo';

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'X-Recruiter-Key': recruiterKey,
    'X-Recruiter-Id': recruiterId,
  },
});

const blockDefinitions: Array<[QuestionBlockKey, string]> = [
  ['hard_skills', 'Hard skills'],
  ['soft_skills', 'Soft skills'],
  ['work_experience', 'Опыт работы'],
];

export function newId(): string {
  return globalThis.crypto?.randomUUID?.()
    ?? `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function newQuestion(kind: 'spoken' | 'coding' = 'spoken'): ConfiguredQuestion {
  return {
    id: newId(),
    text: '',
    kind,
    follow_up_after_answer: false,
    time_limit_seconds: null,
    ...(kind === 'coding' ? { language: 'python' } : {}),
  };
}

export function createDefaultConfiguration(): InterviewConfiguration {
  return {
    schema_version: 1,
    live_coding_enabled: false,
    follow_up_after_all_answers: false,
    blocks: blockDefinitions.map(([key, title]) => ({
      id: newId(), key, title, topic: key, questions: [newQuestion()],
    })),
  };
}

export async function listVacancies(): Promise<Vacancy[]> {
  const response = await api.get<{ vacancies: Vacancy[] }>('/recruiter/vacancies');
  return response.data.vacancies;
}

export async function getVacancy(id: string): Promise<Vacancy> {
  return (await api.get<Vacancy>(`/recruiter/vacancies/${id}`)).data;
}

export async function createVacancy(title: string, description: string): Promise<Vacancy> {
  return (await api.post<Vacancy>('/recruiter/vacancies', description || title, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'X-Vacancy-Title': title,
      'X-Document-Filename': 'vacancy.txt',
      'Idempotency-Key': `cabinet-${newId()}`,
    },
  })).data;
}

export async function getConfiguration(id: string): Promise<InterviewConfiguration> {
  return (await api.get<InterviewConfiguration>(
    `/recruiter/vacancies/${id}/interview-configuration`,
  )).data;
}

export async function saveConfiguration(
  id: string,
  configuration: InterviewConfiguration,
): Promise<InterviewConfiguration> {
  return (await api.put<InterviewConfiguration>(
    `/recruiter/vacancies/${id}/interview-configuration`, configuration,
  )).data;
}

export async function createInvitation(
  vacancyId: string,
  candidateAlias: string | null = null,
): Promise<InvitationCreated> {
  return (await api.post<InvitationCreated>(
    `/recruiter/vacancies/${vacancyId}/invitations`,
    { candidate_alias: candidateAlias, expires_in_hours: 72 },
  )).data;
}

export async function listInterviewResults(vacancyId: string): Promise<InterviewResultSummary[]> {
  return (await api.get<{ interviews: InterviewResultSummary[] }>(`/recruiter/vacancies/${vacancyId}/interviews`)).data.interviews;
}

export async function getInterviewResult(vacancyId: string, sessionId: string): Promise<InterviewResultDetail> {
  return (await api.get<InterviewResultDetail>(`/recruiter/vacancies/${vacancyId}/interviews/${sessionId}`)).data;
}

export default api;
