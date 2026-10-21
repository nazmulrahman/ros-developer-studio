const KEY = "rds.token";
export const getToken = () => sessionStorage.getItem(KEY) ?? "";
export const setToken = (t: string) => sessionStorage.setItem(KEY, t);

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(path, { ...init, headers: { ...(init.headers ?? {}), Authorization: `Bearer ${getToken()}` } });
  if (!r.ok) {
    let msg = r.statusText;
    try { const b = await r.json(); msg = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail); } catch { /* non-JSON error body */ }
    throw new ApiError(r.status, msg);
  }
  return r.json() as Promise<T>;
}
export const health = () => fetch("/api/health").then(r => r.json() as Promise<{ status: string; version: string }>);

let activeBag: string | null = null;
export const setApiBag = (id: string | null) => { activeBag = id; };
export const topicApi = <T,>(topic: string) => api<T>(activeBag ? `/api/bags/${activeBag}/topic?name=${encodeURIComponent(topic)}` : `/api/live/topic?name=${encodeURIComponent(topic)}`);
