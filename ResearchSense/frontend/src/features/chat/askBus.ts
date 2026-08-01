// A tiny global bus so any "Ask AI" / "Ask ResearchSense" control anywhere in
// the app opens the floating assistant widget (and optionally sends a question)
// instead of navigating to a separate page.

export const ASK_EVENT = "rs:ask";

export interface AskDetail {
  query: string;
}

/** Open the assistant widget; if `query` is non-empty, send it right away. */
export function askAssistant(query = ""): void {
  window.dispatchEvent(new CustomEvent<AskDetail>(ASK_EVENT, { detail: { query } }));
}
