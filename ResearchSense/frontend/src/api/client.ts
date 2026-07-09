// Base HTTP helpers. In dev, Vite proxies /api to FastAPI; in prod set
// VITE_API_BASE to the backend origin.
const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Accepts any plain object of query params (typed filter interfaces included).
export type QueryParams = Record<string, string | number | boolean | null | undefined>;

function buildQuery(params?: object): string {
  if (!params) return "";
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      usp.append(key, String(value));
    }
  }
  const s = usp.toString();
  return s ? `?${s}` : "";
}

export async function get<T>(path: string, params?: object): Promise<T> {
  const res = await fetch(`${BASE}${path}${buildQuery(params)}`);
  if (!res.ok) throw new ApiError(res.status, `Request failed: ${path}`);
  return res.json() as Promise<T>;
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, `Request failed: ${path}`);
  return res.json() as Promise<T>;
}
