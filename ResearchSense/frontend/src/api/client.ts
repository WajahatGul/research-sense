// Base HTTP helpers. In dev, Vite proxies /api to FastAPI; in prod set
// VITE_API_BASE to the backend origin.
const BASE = import.meta.env.VITE_API_BASE ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

// Requests must never hang forever. On free hosting the backend sleeps after
// inactivity and a cold start can take ~30-60s; past that we give up with a
// clear message instead of leaving the UI stuck (e.g. "thinking…").
const REQUEST_TIMEOUT_MS = 45000;

async function fetchWithTimeout(url: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError(
        504,
        "The server took too long to respond. It may be waking up from sleep — " +
          "please wait a moment and try again.",
      );
    }
    throw new ApiError(0, "Could not reach the server. Please check your connection and try again.");
  } finally {
    clearTimeout(timer);
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
    // A handler's own HTTPException carries a ready, human string.
    if (typeof detail === "string" && detail.trim()) return detail;
    // A 422 validation error is a list of {loc, msg, type}. Its msg can be a
    // raw pydantic artifact ("String should match pattern '^\\d{4}...'") — turn
    // that into something a person can act on instead of leaking the regex.
    if (Array.isArray(detail) && detail[0]) return friendlyValidation(detail[0]);
  } catch {
    /* body was not JSON; fall through to a status-based message */
  }
  if (res.status >= 500) return "The server had a problem. Please try again.";
  if (res.status === 404) return "Not found.";
  return "Something went wrong. Please try again.";
}

function friendlyValidation(err: { loc?: unknown[]; msg?: string; type?: string }): string {
  const field = String(err.loc?.[err.loc.length - 1] ?? "");
  const msg = err.msg ?? "";
  if (field === "orcid_id" || /ORCID/i.test(msg)) {
    return "Enter a valid 16-digit ORCID iD, e.g. 0000-0002-1825-0097.";
  }
  if (field === "password") {
    return "Password must be at least 8 characters.";
  }
  // Never surface pydantic's internal phrasing (regex patterns, "Value error,").
  if (/^(String should match pattern|Value error,|Input should)/.test(msg)) {
    return "Please check the details you entered and try again.";
  }
  return msg || "Please check the details you entered and try again.";
}

export async function get<T>(path: string, params?: object): Promise<T> {
  const res = await fetchWithTimeout(`${BASE}${path}${buildQuery(params)}`);
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return res.json() as Promise<T>;
}

export async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetchWithTimeout(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res));
  return res.json() as Promise<T>;
}
