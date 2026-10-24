import * as SecureStore from 'expo-secure-store';

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000';
const TOKEN_KEY = 'session_token';

export type UserProfile = {
  id: string;
  email: string;
  name: string;
  timezone: string;
  language: 'auto' | 'ta-IN' | 'en-IN';
  reminder_minutes: number[];
  work_start: string;
  work_end: string;
  work_days: number[];
  morning_briefing_time: string | null;
};

export type CalendarEvent = {
  id: string;
  title: string;
  start: string;
  end: string;
  all_day: boolean;
  location: string | null;
  meet_link: string | null;
  attendees: { email: string; response: string }[];
  my_response: string;
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export const getToken = () => SecureStore.getItemAsync(TOKEN_KEY);
export const saveToken = (token: string) => SecureStore.setItemAsync(TOKEN_KEY, token);
export const clearToken = () => SecureStore.deleteItemAsync(TOKEN_KEY);

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(res.status, typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  signIn: (serverAuthCode: string, timezone: string) =>
    request<{ token: string; user: UserProfile }>('/auth/google', {
      method: 'POST',
      body: JSON.stringify({ server_auth_code: serverAuthCode, timezone }),
    }),
  me: () => request<UserProfile>('/me'),
  updateSettings: (settings: Partial<UserProfile> & { disable_morning_briefing?: boolean }) =>
    request<UserProfile>('/me/settings', { method: 'PUT', body: JSON.stringify(settings) }),
  savePushToken: (token: string) =>
    request<{ ok: boolean }>('/me/push-token', { method: 'POST', body: JSON.stringify({ token }) }),
  upcoming: (days = 7) => request<{ events: CalendarEvent[] }>(`/events/upcoming?days=${days}`),
  chat: (message: string, conversationId: string | null) =>
    request<{ conversation_id: string; reply: string }>('/agent/chat', {
      method: 'POST',
      body: JSON.stringify({ message, conversation_id: conversationId }),
    }),
};
