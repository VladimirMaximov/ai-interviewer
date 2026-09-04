export type Invitation = { session_id: string; consented: boolean };
export type UploadGrant = { response_id: string; storage_key: string; upload_url: string };
export type Transcript = { status: "pending" | "processing" | "completed" | "failed"; text: string | null };

export class CandidateApi {
  constructor(private readonly baseUrl = "/candidate") {}

  async resolve(secret: string): Promise<Invitation> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}`); }
  async consent(secret: string): Promise<Invitation> { return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/consent`, { method: "POST" }); }
  async uploadGrant(secret: string, questionId: string, contentType: string): Promise<UploadGrant> {
    return this.request(`${this.baseUrl}/${encodeURIComponent(secret)}/upload-grants`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question_id: questionId, content_type: contentType }) });
  }
  async upload(url: string, audio: Blob): Promise<void> {
    const response = await fetch(url, { method: "PUT", headers: { "Content-Type": audio.type || "audio/webm" }, body: audio });
    if (!response.ok) throw new Error("Не удалось загрузить аудиоответ.");
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
