import { getToken } from "./auth";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${await getToken()}`);
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = res.status === 429 ? "Too many requests. Please wait and try again." : "Something went wrong. Please try again.";
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || msg;
    } catch { /* keep default message */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  get: <T,>(p: string) => call<T>(p),
  post: <T,>(p: string, body?: unknown) => call<T>(p, json("POST", body)),
  patch: <T,>(p: string, body?: unknown) => call<T>(p, json("PATCH", body)),
  form: <T,>(p: string, fd: FormData) => call<T>(p, { method: "POST", body: fd }),
};
