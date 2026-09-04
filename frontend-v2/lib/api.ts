import type { ApiError, ChatResponse, Conversation, ConversationDetail, ConversationList, DocumentItem, Session, SpeechJob, StudyArtifact } from "@/types/api";

export const API_URL = (process.env.NEXT_PUBLIC_EVA_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class EvaApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { ...(init.body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiError;
    throw new EvaApiError(response.status, payload.error?.code || "request_failed", payload.error?.message || payload.detail || "Request failed");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  login: (identifier: string, password: string) => request<Session>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ identifier, password }) }),
  refresh: () => request<Session>("/api/v1/auth/refresh", { method: "POST" }),
  logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  conversations: (token: string) => request<ConversationList>("/api/v1/conversations", {}, token),
  conversation: (id: string, token: string) => request<ConversationDetail>(`/api/v1/conversations/${id}`, {}, token),
  createConversation: (token: string, title?: string) => request<Conversation>("/api/v1/conversations", { method: "POST", body: JSON.stringify({ title: title || null }) }, token),
  sendMessage: (id: string, content: string, token: string) => request<ChatResponse>(`/api/v1/conversations/${id}/messages`, { method: "POST", body: JSON.stringify({ content }) }, token),
  documents: (token: string) => request<{ items: DocumentItem[]; total: number }>("/api/v1/documents?limit=100", {}, token),
  generateStudy: (payload: Record<string, unknown>, token: string) => request<StudyArtifact>("/api/v1/study/generate", { method: "POST", body: JSON.stringify(payload) }, token),
  synthesize: (text: string, language: string, token: string) => request<{ job_id: string; status: string }>("/api/v1/speech/synthesize", { method: "POST", body: JSON.stringify({ text, language }) }, token),
  speechJob: (id: string, token: string) => request<SpeechJob>(`/api/v1/speech/jobs/${id}`, {}, token),
  speechAudio: async (id: string, token: string) => {
    const response = await fetch(`${API_URL}/api/v1/speech/attachments/${id}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!response.ok) throw new EvaApiError(response.status, "audio_unavailable", "Generated audio is unavailable");
    return response.blob();
  },
};
