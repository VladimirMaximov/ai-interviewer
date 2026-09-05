export type QuestionKind = 'spoken' | 'coding';
export type QuestionBlockKey = 'hard_skills' | 'soft_skills' | 'work_experience';

export interface ConfiguredQuestion {
  id: string;
  text: string;
  kind: QuestionKind;
  follow_up_after_answer: boolean;
  time_limit_seconds: number | null;
  position?: number;
  language?: string;
}

export interface QuestionBlock {
  id: string;
  key: QuestionBlockKey;
  title: string;
  topic: string;
  questions: ConfiguredQuestion[];
  position?: number;
}

export interface InterviewConfiguration {
  schema_version: number;
  live_coding_enabled: boolean;
  follow_up_after_all_answers: boolean;
  blocks: QuestionBlock[];
}

export interface Vacancy {
  id: string;
  title: string;
  status: 'active' | 'closed';
  source_filename: string;
  media_type: string;
  content_hash: string;
  created_at: string;
}

export interface InvitationCreated {
  invitation_id: string;
  vacancy_id: string;
  candidate_token: string;
  candidate_url: string;
  expires_at: string;
}

export interface LeaderboardItem {
  name: string;
  score: number;
}

export interface InterviewResultSummary {
  session_id: string | null; invitation_id: string; candidate_alias: string | null;
  status: 'invited' | 'in_progress' | 'processing' | 'completed'; score: number | null;
  answered_questions: number; total_questions: number; expires_at: string; submitted_at: string | null;
}

export interface InterviewResultDetail {
  summary: InterviewResultSummary; vacancy_title: string; recording_duration_ms: number | null;
  media: Array<{ sequence: number; start_offset_ms: number; end_offset_ms: number; content_type: string; url: string }>;
  answers: Array<{ response_id: string; question_id: string; question_text: string; question_kind: 'spoken' | 'coding'; is_follow_up: boolean; transcription_status: 'pending' | 'processing' | 'completed' | 'failed'; transcript_text: string | null; start_offset_ms: number | null; end_offset_ms: number | null; timed_out: boolean; code: null | { language: string; source_code: string } }>;
  monitoring_events: Array<{ id: string; response_id: string; question_id: string; kind: string; started_at_ms: number; ended_at_ms: number; review_status: string; evidence_url: string | null }>;
  assessment: Record<string, unknown> | null;
}
