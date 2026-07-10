import { useState } from "react";
import { Link } from "react-router-dom";

import { sendChat } from "../../api/chat";
import type { ChatSource } from "../../types";
import styles from "./ChatPanel.module.css";

interface Turn {
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
}

const SUGGESTIONS = [
  "Who works on machine learning?",
  "Show cybersecurity researchers",
  "Find work on Internet of Things",
];

// Strip decorations the chat adds to source labels ("Paper: " prefix,
// trailing "(2022)") so the title can be used as a publications search query.
function titleFromLabel(label: string): string {
  return label
    .replace(/^Paper:\s*/i, "")
    .replace(/\s*\(\d{4}\)\s*$/, "")
    .trim();
}

function sourceLink(s: ChatSource): string {
  switch (s.kind) {
    case "researcher":
      return s.ref_id ? `/researchers/${s.ref_id}` : "/researchers";
    case "topic":
      return s.ref_id ? `/publications?topic_id=${s.ref_id}` : "/topics";
    case "publication":
      return `/publications?q=${encodeURIComponent(titleFromLabel(s.label))}`;
    case "paper":
      // Full-text papers may not be in the publications table, so the
      // reliable landing is the author's profile.
      return s.ref_id
        ? `/researchers/${s.ref_id}`
        : `/publications?q=${encodeURIComponent(titleFromLabel(s.label))}`;
    case "project":
      return "/projects";
    default:
      return "/researchers";
  }
}

export function ChatPanel() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async (message: string) => {
    if (!message.trim() || busy) return;
    // Recent turns travel with the request so follow-up questions work.
    const history = turns.slice(-6).map((t) => ({
      role: t.role,
      content: t.text,
    }));
    setTurns((t) => [...t, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await sendChat(message, history);
      setTurns((t) => [
        ...t,
        { role: "assistant", text: res.answer, sources: res.sources },
      ]);
    } catch {
      setTurns((t) => [
        ...t,
        { role: "assistant", text: "The assistant is unavailable. Is the API running?" },
      ]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.panel}>
      <div className={styles.thread}>
        {turns.length === 0 && (
          <div className={styles.empty}>
            <p className={styles.emptyLead}>
              Ask about researchers, areas, or who to collaborate with.
            </p>
            <div className={styles.suggest}>
              {SUGGESTIONS.map((s) => (
                <button key={s} className={styles.chip} onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {turns.map((turn, i) => (
          <div key={i} className={styles[turn.role]}>
            <span className={styles.author}>
              {turn.role === "user" ? "You" : "ResearchSense"}
            </span>
            <p className={styles.bubble}>{turn.text}</p>
            {turn.sources && turn.sources.length > 0 && (
              <div className={styles.sources}>
                {turn.sources.map((s, j) => (
                  <Link key={j} to={sourceLink(s)} className={styles.source}>
                    {s.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
        {busy && <span className={styles.typing}>ResearchSense is thinking…</span>}
      </div>

      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          className={styles.input}
          value={input}
          placeholder="Ask a question…"
          onChange={(e) => setInput(e.target.value)}
        />
        <button type="submit" className={styles.send} disabled={busy}>
          Send
        </button>
      </form>
    </div>
  );
}
