export type User = { id: string; username: string; email: string; full_name: string | null; role: string; profile_type: string };
export type Session = { access_token: string; token_type: "bearer"; expires_in: number; user: User };
export type Message = { id: string; conversation_id: string; role: "user" | "assistant" | "system"; content: string; language: string | null; intent: string | null; status: string; created_at: string };
export type Conversation = { id: string; title: string | null; language: string | null; created_at: string; updated_at: string };
export type ConversationDetail = Conversation & { messages: Message[] };
export type ConversationList = { items: Conversation[]; total: number };
export type ChatResponse = { user_message: Message; assistant_message: Message };
export type ApiError = { error?: { code?: string; message?: string }; detail?: string };
