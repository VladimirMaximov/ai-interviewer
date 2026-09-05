export type Invitation = { session_id: string; consented: boolean };
export type UploadGrant = { response_id: string; storage_key: string; upload_url: string };
export type Transcript = { status: "pending" | "processing" | "completed" | "failed"; text: string | null };
export type InterviewQuestion = { question_id: string; prompt: string; kind: "baseline" | "personalized" | "follow_up" | "live_coding" };
export type InterviewQuestionPlan = { agent_session_id: string; questions: InterviewQuestion[] };
export type LiveCodingSubmission = { response_id: string; question_id: string; status: "completed" };
export type BrowserMonitoringEventKind =
  | "face_missing"
  | "multiple_faces"
  | "face_detection_unavailable";
export type MonitoringEvidenceGrant = { client_event_id: string; upload_url: string };
export type MonitoringEventInput = {
  client_event_id: string;
  response_id: string;
  question_id: string;
  kind: BrowserMonitoringEventKind;
  started_at_ms: number;
  ended_at_ms: number;
  confidence?: number;
  detector_name: string;
  detector_version: string;
  evidence_content_type?: string;
  evidence_checksum?: string;
};
export type MonitoringEvent = {
  id: string;
  kind: BrowserMonitoringEventKind;
  started_at_ms: number;
  ended_at_ms: number;
  review_status: "pending" | "confirmed" | "dismissed";
};
export type FeedbackEvidence = { excerpt: string | null };
export type FeedbackPoint = { title: string; detail: string; evidence: FeedbackEvidence[] };
export type FeedbackGrowthArea = FeedbackPoint & { action: string };
export type ExperienceAlignmentStatus = "confirmed" | "partially_confirmed" | "not_confirmed" | "not_assessed";
export type FeedbackExperienceAlignment = FeedbackPoint & { status: ExperienceAlignmentStatus };
export type CandidateFeedback = {
  score: { value: number | null; maximum: 10; scale_version: "signed_readiness_to_10_v1"; evidence_coverage: number; explanation: string };
  headline: string;
  summary: string;
  strengths: FeedbackPoint[];
  growth_areas: FeedbackGrowthArea[];
  experience_alignment: FeedbackExperienceAlignment[];
  alternative_vacancy: null | {
    vacancy_id: string;
    title: string;
    matched_areas: string[];
    message: string;
    is_automatic_transfer: false;
  };
  next_steps: string[];
  limitations: string[];
  published_at: string;
};
export type CandidateFeedbackDelivery = {
  status: "pending_review" | "published";
  feedback: CandidateFeedback | null;
};

export class CandidateApi {
  constructor(private readonly baseUrl = "/candidate") {}

  async resolve(secret: string): Promise<Invitation> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}`); }
  async consent(secret: string): Promise<Invitation> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/consent`, { method: "POST" }); }
  async questions(secret: string): Promise<InterviewQuestionPlan> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/questions`); }
  async submitLiveCoding(secret: string, questionId: string, code: string): Promise<LiveCodingSubmission> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/live-coding-responses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id: questionId, code }),
    });
  }
  async feedback(secret: string): Promise<CandidateFeedbackDelivery> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/feedback`); }
  async uploadGrant(secret: string, questionId: string, contentType: string): Promise<UploadGrant> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/upload-grants`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question_id: questionId, content_type: contentType }) });
  }
  async monitoringEvidenceGrant(secret: string, clientEventId: string, responseId: string, questionId: string, contentType: string): Promise<MonitoringEvidenceGrant> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/monitoring-evidence-grants`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_event_id: clientEventId, response_id: responseId, question_id: questionId, content_type: contentType }),
    });
  }
  async recordMonitoringEvent(secret: string, event: MonitoringEventInput): Promise<MonitoringEvent> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/monitoring-events`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
  }
  async upload(url: string, media: Blob): Promise<void> {
    const response = await fetch(url, { method: "PUT", headers: { "Content-Type": media.type || "application/octet-stream" }, body: media });
    if (!response.ok) throw new Error("Не удалось загрузить запись.");
  }
  async confirm(secret: string, responseId: string, checksum: string): Promise<Transcript> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/responses/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ response_id: responseId, checksum }) });
  }
  async transcript(secret: string, responseId: string): Promise<Transcript> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/responses/${responseId}/transcript`); }

  private async request<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, init);
    if (!response.ok) throw new Error("Ссылка интервью недоступна или запрос не выполнен.");
    return response.json() as Promise<T>;
  }
}
