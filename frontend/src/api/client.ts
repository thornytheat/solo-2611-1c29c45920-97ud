/** 统一 /api 前缀的 fetch 封装：JWT 注入、401 清理、错误归一。 */
import { authStore } from '../stores/authStore';

export class ApiError extends Error {
  status: number;
  code: string;
  payload: unknown;

  constructor(status: number, payload: unknown) {
    const body = payload as { code?: string; message?: string } | null;
    super(body?.message ?? `请求失败（${status}）`);
    this.status = status;
    this.code = body?.code ?? 'ERROR';
    this.payload = payload;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = authStore.getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`/api${path}`, { ...init, headers });
  if (response.status === 401) {
    authStore.logout();
  }
  const text = await response.text();
  const data = text ? safeParse(text) : null;
  if (!response.ok) {
    throw new ApiError(response.status, data);
  }
  return data as T;
}

function safeParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const http = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
};
