export type AlertKind = "publications" | "researchers";

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Something went wrong. Please try again.");
  return data as T;
}

export const keepSearch = (email: string, kind: AlertKind, filters: Record<string, string | number | undefined>) =>
  post<{ status: string }>("/api/alerts", { email, kind, filters });

export const confirmAlert = (token: string) =>
  post<{ status: string; search: string }>("/api/alerts/confirm", { token });

export const stopAlert = (token: string) =>
  post<{ status: string; search: string }>("/api/alerts/stop", { token });
