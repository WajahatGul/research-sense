// Who the browser is currently signed in as, and what stored state belongs to
// them. The assistant keeps its conversation in localStorage so it survives
// minimising and page changes — which means the conversation must be tied to
// the institution it was had with, and must not outlive signing out. Otherwise
// the next person at a shared computer reads the last institution's research.

/** Fired whenever the signed-in workspace changes (sign in, sign out). */
export const SESSION_EVENT = "rs:session";

const CHAT_TURNS_PREFIX = "rs_chat_turns";

/** The anonymous visitor and every institution get their own conversation. */
export function chatTurnsKey(workspaceId?: string | null): string {
  return `${CHAT_TURNS_PREFIX}:${workspaceId || "demo"}`;
}

/** Drop one workspace's stored conversation (called when it signs out). */
export function forgetChat(workspaceId?: string | null): void {
  try {
    localStorage.removeItem(chatTurnsKey(workspaceId));
  } catch {
    /* storage unavailable — nothing was stored to begin with */
  }
}

/** Tell the live parts of the app (the assistant) that the session changed. */
export function announceSession(): void {
  window.dispatchEvent(new Event(SESSION_EVENT));
}
