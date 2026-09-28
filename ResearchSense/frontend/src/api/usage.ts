// Anonymous usage counts (see backend usage_service). The visitor id is a
// random value this browser makes up and keeps; it names no one. Reporting
// never blocks or breaks the page: failures are ignored.

const KEY = "rs-visitor";

function visitorId(): string {
  try {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(KEY, id);
    }
    return id;
  } catch {
    return ""; // storage blocked: count nothing rather than guess
  }
}

export function track(kind: "visit" | "claim_started", detail = ""): void {
  const visitor = visitorId();
  if (!visitor) return;
  try {
    void fetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind, visitor, detail }),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    /* never let counting break the page */
  }
}
