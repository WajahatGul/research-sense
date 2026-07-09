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

function sourceLink(s: ChatSource): string {
  if (s.kind === "researcher" && s.ref_id) return `/researchers/${s.ref_id}`;
  if (s.kind === "topic" && s.ref_id) return `/publications?topic_id=${s.ref_id}`;
  return "/researchers";
}

export function ChatPanel() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async (message: string) => {
    if (!message.trim() || busy) return;
    setTurns((t) => [...t, { role: "user", text: message }]);
    setInput("");
    setBusy(true);
    try {
      const res = await sendChat(message);
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
