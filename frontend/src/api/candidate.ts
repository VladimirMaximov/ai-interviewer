export type CandidateQuestion = { id: string; text: string; kind: "spoken" | "coding"; block_key: string | null; block_title: string | null; time_limit_seconds: number | null };
export type Invitation = { session_id: string; consented: boolean; questions: CandidateQuestion[] };
export type UploadGrant = { response_id: string; storage_key: string; upload_url: string };
export type Transcript = { status: "pending" | "processing" | "completed" | "failed"; text: string | null };
export type RecordingGrant = { recording_id: string; storage_key: string; upload_url: string; content_type: string };
export type ResponseSegment = { response_id: string; status: Transcript["status"] };
export type RecordingChunkGrant = { chunk_id: string; upload_url: string; content_type: string };
export type FollowUpQuestion = { id: string; source_response_id: string | null; text: string; status: "ready" | "presented" | "answered" };
export type PresenterState = {
  question_id: string;
  status: "queued" | "audio_processing" | "audio_ready" | "avatar_processing" | "ready" | "failed";
  audio_url: string | null;
  avatar_url: string | null;
  static_portrait_url: string;
  fallback: "none" | "static_portrait" | "browser_speech";
};
export type InterviewQuestion = { question_id: string; prompt: string; kind: "baseline" | "personalized" | "follow_up" | "live_coding" };
export type InterviewQuestionPlan = { agent_session_id: string; questions: InterviewQuestion[] };
export type LiveCodingSubmission = { response_id: string; question_id: string; status: "completed" };
export type BrowserMonitoringEventKind = "face_missing" | "multiple_faces" | "face_detection_unavailable";
export type MonitoringEvidenceGrant = { client_event_id: string; upload_url: string };
export type MonitoringEventInput = {
  client_event_id: string; response_id: string; question_id: string;
  kind: BrowserMonitoringEventKind; started_at_ms: number; ended_at_ms: number;
  confidence?: number; detector_name: string; detector_version: string;
  evidence_content_type?: string; evidence_checksum?: string;
};
export type MonitoringEvent = { id: string; kind: BrowserMonitoringEventKind; started_at_ms: number; ended_at_ms: number; review_status: "pending" | "confirmed" | "dismissed" };
export type FeedbackEvidence = { excerpt: string | null };
export type FeedbackPoint = { title: string; detail: string; evidence: FeedbackEvidence[] };
export type FeedbackGrowthArea = FeedbackPoint & { action: string };
export type ExperienceAlignmentStatus = "confirmed" | "partially_confirmed" | "not_confirmed" | "not_assessed";
export type FeedbackExperienceAlignment = FeedbackPoint & { status: ExperienceAlignmentStatus };
export type CandidateFeedback = {
  score: { value: number | null; maximum: 10; scale_version: "signed_readiness_to_10_v1"; evidence_coverage: number; explanation: string };
  headline: string; summary: string; strengths: FeedbackPoint[]; growth_areas: FeedbackGrowthArea[];
  experience_alignment: FeedbackExperienceAlignment[];
  alternative_vacancy: null | { vacancy_id: string; title: string; matched_areas: string[]; message: string; is_automatic_transfer: false };
  next_steps: string[]; limitations: string[]; published_at: string;
};
export type CandidateFeedbackDelivery = { status: "pending_review" | "published"; feedback: CandidateFeedback | null };

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
  async upload(url: string, audio: Blob, contentType = audio.type || "audio/webm"): Promise<void> {
    const response = await fetch(url, { method: "PUT", headers: { "Content-Type": contentType }, body: audio });
    if (!response.ok) throw new Error("Не удалось загрузить аудиоответ.");
  }
  async confirm(secret: string, responseId: string, checksum: string): Promise<Transcript> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/responses/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ response_id: responseId, checksum }) });
  }
  async transcript(secret: string, responseId: string): Promise<Transcript> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/responses/${responseId}/transcript`); }
  async monitoringEvidenceGrant(secret: string, clientEventId: string, responseId: string, questionId: string, contentType: string): Promise<MonitoringEvidenceGrant> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/monitoring-evidence-grants`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ client_event_id: clientEventId, response_id: responseId, question_id: questionId, content_type: contentType }) });
  }
  async recordMonitoringEvent(secret: string, event: MonitoringEventInput): Promise<MonitoringEvent> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/monitoring-events`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(event) });
  }
  async timeline(secret: string, eventType: string, recordingOffsetMs: number, questionId?: string): Promise<void> {
    await this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/timeline-events`, { method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true, body: JSON.stringify({ question_id: questionId, event_type: eventType, recording_offset_ms: recordingOffsetMs }) });
  }
  async startRecording(secret: string, contentType: string): Promise<RecordingGrant> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/recording`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content_type: contentType }) });
  }
  async finishRecording(secret: string, recordingId: string, checksum: string): Promise<void> {
    await this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/recording/finish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ recording_id: recordingId, checksum }) });
  }
  async recordingChunkGrant(secret: string, recordingId: string, sequence: number, startOffsetMs: number, endOffsetMs: number, contentType: string): Promise<RecordingChunkGrant> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/recording/chunks`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ recording_id: recordingId, sequence, start_offset_ms: startOffsetMs, end_offset_ms: endOffsetMs, content_type: contentType }) });
  }
  async confirmRecordingChunk(secret: string, chunkId: string, checksum: string): Promise<void> {
    await this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/recording/chunks/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ chunk_id: chunkId, checksum }) });
  }
  async saveSegment(secret: string, questionId: string, startOffsetMs: number, endOffsetMs: number, timedOut = false): Promise<ResponseSegment> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/responses/segments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question_id: questionId, start_offset_ms: startOffsetMs, end_offset_ms: endOffsetMs, timed_out: timedOut }) });
  }
  async saveCodeAnswer(secret: string, questionId: string, language: string, sourceCode: string, startOffsetMs: number, endOffsetMs: number, timedOut = false): Promise<ResponseSegment> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/code-answers`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question_id: questionId, language, source_code: sourceCode, start_offset_ms: startOffsetMs, end_offset_ms: endOffsetMs, timed_out: timedOut }) });
  }
  async followUps(secret: string): Promise<FollowUpQuestion[]> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/follow-ups`); }
  async presenter(secret: string, questionId: string): Promise<PresenterState> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/questions/${encodeURIComponent(questionId)}/presenter`);
  }
  async waitForPresenter(secret: string, questionId: string, timeoutMs = 12_000): Promise<PresenterState> {
    const deadline = Date.now() + timeoutMs;
    let state = await this.presenter(secret, questionId);
    while (!state.audio_url && state.status !== "failed" && Date.now() < deadline) {
      await new Promise((resolve) => window.setTimeout(resolve, 500));
      state = await this.presenter(secret, questionId);
    }
    return state;
  }
  questionSpeechUrl(secret: string, questionId: string): string {
    return `${this.baseUrl}/${encodeURIComponent(secret)}/questions/${encodeURIComponent(questionId)}/speech`;
  }
  questionAvatarUrl(secret: string, questionId: string): string {
    return `${this.baseUrl}/${encodeURIComponent(secret)}/questions/${encodeURIComponent(questionId)}/avatar`;
  }
  questionAvatarFrameUrl(secret: string, questionId: string, frame: "idle" | "speaking"): string {
    return `${this.baseUrl}/${encodeURIComponent(secret)}/questions/${encodeURIComponent(questionId)}/avatar-frame/${frame}`;
  }

  private async request<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, init);
    if (!response.ok) throw new Error("Ссылка интервью недоступна или запрос не выполнен.");
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
}
