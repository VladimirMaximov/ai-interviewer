export type Invitation = { session_id: string; consented: boolean };
export type UploadGrant = { response_id: string; storage_key: string; upload_url: string };
export type Transcript = { status: "pending" | "processing" | "completed" | "failed"; text: string | null };
export type RecordingGrant = { recording_id: string; storage_key: string; upload_url: string; content_type: string };
export type ResponseSegment = { response_id: string; status: Transcript["status"] };
export type RecordingChunkGrant = { chunk_id: string; upload_url: string; content_type: string };
export type FollowUpQuestion = { id: string; source_response_id: string | null; text: string; status: "ready" | "presented" | "answered" };

export class CandidateApi {
  constructor(private readonly baseUrl = "/candidate") {}

  async resolve(secret: string): Promise<Invitation> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}`); }
  async consent(secret: string): Promise<Invitation> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/consent`, { method: "POST" }); }
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
  async saveSegment(secret: string, questionId: string, startOffsetMs: number, endOffsetMs: number): Promise<ResponseSegment> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/responses/segments`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question_id: questionId, start_offset_ms: startOffsetMs, end_offset_ms: endOffsetMs }) });
  }
  async followUps(secret: string): Promise<FollowUpQuestion[]> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/follow-ups`); }

  private async request<T>(url: string, init?: RequestInit): Promise<T> {
    const response = await fetch(url, init);
    if (!response.ok) throw new Error("Ссылка интервью недоступна или запрос не выполнен.");
    if (response.status === 204) return undefined as T;
    return response.json() as Promise<T>;
  }
}
