import type { ApiError, CallSession, CallTicket, ChatResponse, Conversation, ConversationDetail, ConversationList, DocumentAnswer, DocumentContent, DocumentItem, DocumentSource, DocumentSummary, DocumentUpload, ProcessingJob, Session, SpeechJob, StudyArtifact, StudyArtifactList, Transcription, TranscriptionUpload, Translation, TranslationResult, VoiceConsent, VoiceProfile } from "@/types/api";

export const API_URL = (process.env.NEXT_PUBLIC_EVA_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class EvaApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  let response: Response;
  const isFormData = typeof FormData !== "undefined" && init.body instanceof FormData;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      credentials: "include",
      headers: { ...(init.body && !isFormData ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
    });
  } catch {
    throw new EvaApiError(0, "network_error", "EVA cannot reach the server. Check that the API is running, then try again.");
  }
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiError;
    throw new EvaApiError(response.status, payload.error?.code || "request_failed", payload.error?.message || payload.detail || "Request failed");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  login: (identifier: string, password: string) => request<Session>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ identifier, password }) }),
  register: (payload: { username: string; email: string; password: string; full_name: string }) => request<Session>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  forgotPassword: (identifier: string) => request<{ message: string; reset_token?: string | null }>("/api/v1/auth/forgot-password", { method: "POST", body: JSON.stringify({ identifier }) }),
  resetPassword: (token: string, newPassword: string) => request<{ message: string }>("/api/v1/auth/reset-password", { method: "POST", body: JSON.stringify({ token, new_password: newPassword }) }),
  refresh: () => request<Session>("/api/v1/auth/refresh", { method: "POST" }),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  conversations: (token: string) => request<ConversationList>("/api/v1/conversations", {}, token),
  conversation: (id: string, token: string) => request<ConversationDetail>(`/api/v1/conversations/${id}`, {}, token),
  createConversation: (token: string, title?: string) => request<Conversation>("/api/v1/conversations", { method: "POST", body: JSON.stringify({ title: title || null }) }, token),
  sendMessage: (id: string, content: string, token: string) => request<ChatResponse>(`/api/v1/conversations/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) }, token),
  streamMessage: async (id: string, content: string, token: string, onDelta: (text: string) => void) => {
    let response: Response;
    try {
      response = await fetch(`${API_URL}/api/v1/conversations/${id}/messages/stream`, {
        method: "POST", credentials: "include",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ content }),
      });
    } catch {
      throw new EvaApiError(0, "network_error", "EVA cannot reach the server. Please try again.");
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as ApiError;
      throw new EvaApiError(response.status, payload.error?.code || "request_failed", payload.error?.message || "EVA could not answer.");
    }
    if (!response.body) throw new EvaApiError(0, "stream_unavailable", "Your browser could not open the response stream.");
    const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = "";
    while (true) {
      const { value, done } = await reader.read(); buffer += decoder.decode(value, { stream: !done });
      const events = buffer.split("\n\n"); buffer = events.pop() || "";
      for (const block of events) {
        const event = block.split("\n").find((line) => line.startsWith("event: "))?.slice(7);
        const raw = block.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
        if (!raw) continue;
        const data = JSON.parse(raw) as { text?: string; message?: string; code?: string };
        if (event === "delta" && data.text) onDelta(data.text);
        if (event === "error") throw new EvaApiError(502, data.code || "stream_error", data.message || "EVA could not complete the response.");
      }
      if (done) break;
    }
  },
  documents: (token: string) => request<{ items: DocumentItem[]; total: number }>("/api/v1/documents?limit=100", {}, token),
  uploadDocument: async (file: File, token: string) => {
    const form = new FormData(); form.append("file", file);
    return request<DocumentUpload>("/api/v1/documents", { method: "POST", body: form }, token);
  },
  documentJob: (id: string, token: string) => request<ProcessingJob>(`/api/v1/documents/jobs/${id}`, {}, token),
  documentContent: (id: string, token: string) => request<DocumentContent>(`/api/v1/documents/${id}/content`, {}, token),
  searchDocument: (query: string, documentId: string | null, token: string) => request<DocumentSource[]>("/api/v1/documents/search", { method: "POST", body: JSON.stringify({ query, document_id: documentId, limit: 8 }) }, token),
  askDocument: (query: string, documentId: string | null, token: string) => request<DocumentAnswer>("/api/v1/documents/ask", { method: "POST", body: JSON.stringify({ query, document_id: documentId, limit: 8 }) }, token),
  summarizeDocument: (id: string, token: string) => request<DocumentSummary>(`/api/v1/documents/${id}/summary`, { method: "POST" }, token),
  uploadAudio: async (file: File, token: string, language = "auto") => {
    const form = new FormData(); form.append("file", file); form.append("language", language);
    return request<TranscriptionUpload>("/api/v1/speech/transcriptions", { method: "POST", body: form }, token);
  },
  transcription: (id: string, token: string) => request<Transcription>(`/api/v1/speech/transcriptions/${id}`, {}, token),
  generateStudy: (payload: Record<string, unknown>, token: string) => request<StudyArtifact>("/api/v1/study/generate", { method: "POST", body: JSON.stringify(payload) }, token),
  studyArtifacts: (token: string) => request<StudyArtifactList>("/api/v1/study/artifacts?limit=100", {}, token),
  deleteStudyArtifact: (id: string, token: string) => request<void>(`/api/v1/study/artifacts/${id}`, { method: "DELETE" }, token),
  translate: (text: string, sourceLanguage: string | null, targetLanguage: string, mode: string, token: string) => request<TranslationResult>("/api/v1/translations", { method: "POST", body: JSON.stringify({ text, source_language: sourceLanguage, target_language: targetLanguage, mode }) }, token),
  translations: (token: string) => request<{ items: Translation[]; total: number }>("/api/v1/translations?limit=20", {}, token),
  synthesize: (text: string, language: string, token: string, voiceProfileId?: string) => request<{ job_id: string; status: string }>("/api/v1/speech/synthesize", { method: "POST", body: JSON.stringify({ text, language, voice_profile_id: voiceProfileId || null }) }, token),
  speechJob: (id: string, token: string) => request<SpeechJob>(`/api/v1/speech/jobs/${id}`, {}, token),
  speechAudio: async (id: string, token: string) => {
    const response = await fetch(`${API_URL}/api/v1/speech/attachments/${id}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new EvaApiError(response.status, "audio_unavailable", "Generated audio is unavailable");
    return response.blob();
  },
  voiceConsent: () => request<VoiceConsent>("/api/v1/voices/consent"),
  voiceProfiles: (token: string) => request<{ items: VoiceProfile[]; total: number }>("/api/v1/voices", {}, token),
  createVoice: async (form: FormData, token: string) => {
    const response = await fetch(`${API_URL}/api/v1/voices`, { method: "POST", credentials: "include", headers: { Authorization: `Bearer ${token}` }, body: form });
    if (!response.ok) { const payload = await response.json().catch(() => ({})) as ApiError; throw new EvaApiError(response.status, payload.error?.code || "voice_error", payload.error?.message || "Voice profile could not be created"); }
    return response.json() as Promise<VoiceProfile>;
  },
  revokeVoice: (id: string, token: string) => request<VoiceProfile>(`/api/v1/voices/${id}/revoke`, { method: "POST" }, token),
  deleteVoice: (id: string, token: string) => request<void>(`/api/v1/voices/${id}`, { method: "DELETE" }, token),
  exportVoice: async (id: string, token: string) => {
    const response = await fetch(`${API_URL}/api/v1/voices/${id}/export`, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new EvaApiError(response.status, "voice_export_failed", "Voice sample could not be exported");
    return response.blob();
  },
  callTicket: (source_language: string, target_language: string, token: string) => request<CallTicket>("/api/v1/calls/tickets", { method: "POST", body: JSON.stringify({ source_language, target_language }) }, token),
  callSessions: (token: string) => request<CallSession[]>("/api/v1/calls/sessions", {}, token),
};
