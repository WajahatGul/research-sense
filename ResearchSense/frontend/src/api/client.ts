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

// Prefer the API's own error message (FastAPI puts it in "detail") so users
// see "Invalid ORCID iD or password" instead of a generic "Request failed".
async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    const detail = data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  } catch {
    /* body was not JSON; fall through to a status-based message */
  }
  if (res.status >= 500) return "The server had a problem. Please try again.";
  if (res.status === 404) return "Not found.";
  return "Something went wrong. Please try again.";
}

export async function get<T>(path: string, params?: object): Promise<T> {
  const res = await fetch(`${BASE}${path}${buildQuery(params)}`);
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return res.json() as Promise<T>;
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return res.json() as Promise<T>;
}
