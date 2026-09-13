import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";

import { fetchChatSuggestions, sendChat } from "../../api/chat";
import { fetchLibrary } from "../../api/library";
import { getWorkspaceSession } from "../../api/workspace";
import { SESSION_EVENT, chatTurnsKey } from "../../lib/session";
import type { ChatSource } from "../../types";
import styles from "./ChatPanel.module.css";

interface Turn {
  role: "user" | "assistant";
  text: string;
  sources?: ChatSource[];
}

// Strip decorations the chat adds to source labels ("Paper: "/"Library: "
// prefixes, trailing "(2022)") so the title can be used as a search query.
function titleFromLabel(label: string): string {
  return label
    .replace(/^(Paper|Library):\s*/i, "")
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
      // Library papers (unattributed, no ref_id) live on the Library page;
      // faculty papers land on the author's profile.
      if (s.label.startsWith("Library:")) return "/library";
      return s.ref_id
        ? `/researchers/${s.ref_id}`
        : `/publications?q=${encodeURIComponent(titleFromLabel(s.label))}`;
    case "project":
      return "/projects";
    default:
      return "/researchers";
  }
}

// The conversation is kept in localStorage so it survives minimising the
// widget, navigating between pages, and reloads — until the user clears it or
// signs out. The key carries the workspace, so one institution's conversation
// is never shown to the next person to use this browser.
function currentChatKey(): string {
  return chatTurnsKey(getWorkspaceSession()?.workspace_id);
}

function loadTurns(key: string): Turn[] {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Turn[]) : [];
  } catch {
    return [];
  }
}

export function ChatPanel(
  { fill = false, submitSignal, visible = true }:
    {
      fill?: boolean;
      submitSignal?: { text: string; nonce: number };
      visible?: boolean;
    } = {},
) {
  const [chatKey, setChatKey] = useState(currentChatKey);
  const [turns, setTurns] = useState<Turn[]>(() => loadTurns(currentChatKey()));
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const threadRef = useRef<HTMLDivElement>(null);

  // Keep the newest message in view: scroll to the bottom whenever a message
  // arrives, the assistant is thinking, or the panel becomes visible again
  // (e.g. re-opening the minimized widget), so the latest reply is always shown.
  useEffect(() => {
    const el = threadRef.current;
    if (el && visible) el.scrollTop = el.scrollHeight;
  }, [turns, busy, visible]);

  // Signing in or out swaps the whole conversation, so the assistant never
  // shows one institution's research to another.
  useEffect(() => {
    const onSession = () => {
      const key = currentChatKey();
      setChatKey(key);
      setTurns(loadTurns(key));
    };
    window.addEventListener(SESSION_EVENT, onSession);
    return () => window.removeEventListener(SESSION_EVENT, onSession);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(chatKey, JSON.stringify(turns));
    } catch {
      /* storage full or unavailable — the chat still works in memory */
    }
  }, [chatKey, turns]);

  const clearChat = () => {
    setTurns([]);
    try {
      localStorage.removeItem(chatKey);
    } catch {
      /* ignore */
    }
  };

  // Library papers become extra suggestion chips, so studied papers are
  // discoverable right where questions are asked. The reading room belongs to
  // the demo deployment and its full text is not in a workspace's index, so
  // offering it to a signed-in institution would only lead to "not found".
  const inWorkspace = !!getWorkspaceSession();
  const { data: library } = useQuery({
    queryKey: ["library"],
    queryFn: fetchLibrary,
    enabled: !inWorkspace,
  });

  // Starter questions are built from this workspace's own records, so the
  // first thing a new institution clicks is something it can answer.
  const { data: suggestions } = useQuery({
    queryKey: ["chat-suggestions", chatKey],
    queryFn: fetchChatSuggestions,
  });

  // "/ask?q=..." (e.g. the Library page's "Ask about it") prefills the box.
  const [searchParams, setSearchParams] = useSearchParams();
  useEffect(() => {
    const q = searchParams.get("q");
    if (q) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time consumption of the "q" URL param on mount, not a render loop.
      setInput(q);
      setSearchParams({}, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
    } catch (e) {
      // Show the real reason (timeout / server waking / unreachable) rather
      // than a generic line, so the user knows to just wait and retry.
      const text = e instanceof Error && e.message
        ? e.message
        : "The assistant is unavailable right now. Please try again in a moment.";
      setTurns((t) => [...t, { role: "assistant", text }]);
    } finally {
      setBusy(false);
    }
  };

  // An "Ask AI" control elsewhere in the app can hand the widget a question to
  // send. The nonce makes each request fire once, even for the same text.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot send of a queued question (keyed by nonce), not a render loop.
    if (submitSignal?.text) void ask(submitSignal.text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submitSignal?.nonce]);

  return (
    <div className={fill ? `${styles.panel} ${styles.fill}` : styles.panel}>
      {turns.length > 0 && (
        <div className={styles.toolbar}>
          <button type="button" className={styles.clear} onClick={clearChat}>
            Clear chat
          </button>
        </div>
      )}
      <div className={styles.thread} ref={threadRef}>
        {turns.length === 0 && (
          <div className={styles.empty}>
            <p className={styles.emptyLead}>
              {suggestions && suggestions.length === 0
                ? "Add your profile and papers in the Portal, then ask me about them."
                : "Ask about researchers, areas, or who to collaborate with."}
            </p>
            <div className={styles.suggest}>
              {(suggestions ?? []).map((s) => (
                <button key={s} className={styles.chip} onClick={() => ask(s)}>
                  {s}
                </button>
              ))}
              {(inWorkspace ? [] : library ?? []).slice(0, 2).map((p) => (
                <button
                  key={p.filename}
                  className={styles.chip}
                  onClick={() => ask(`Summarize the paper "${p.title}"`)}
                >
                  Summarize "{p.title.length > 44
                    ? p.title.slice(0, 44) + "…" : p.title}"
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
            {turn.role === "assistant" ? (
              <div className={`${styles.bubble} ${styles.markdown}`}>
                <ReactMarkdown>{turn.text}</ReactMarkdown>
              </div>
            ) : (
              <p className={styles.bubble}>{turn.text}</p>
            )}
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
