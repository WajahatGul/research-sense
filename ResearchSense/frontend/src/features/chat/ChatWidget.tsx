import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";

import { PRODUCT_NAME } from "../../config";
import { ASK_EVENT, type AskDetail } from "./askBus";
import { ChatPanel } from "./ChatPanel";
import styles from "./ChatWidget.module.css";

const POS_KEY = "rs_chat_launcher_pos";
const OPEN_KEY = "rs_chat_open";
const SIZE = 58; // launcher diameter
const WIN_W = 384;
const WIN_H = 540;

interface Pos {
  x: number;
  y: number;
}

const MARGIN = 24;

/** Where the launcher sits, stored as a distance from whichever edges it was
 *  dragged nearest to. Absolute coordinates do not survive a resize: a button
 *  clamped to fit a phone stays at those coordinates on a desktop, stranding it
 *  in the middle of the page. Edge distances keep a corner-docked button in
 *  that corner at every size. */
interface Dock {
  dx: number;
  dy: number;
  fromRight: boolean;
  fromBottom: boolean;
}

const clampNum = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, hi));

function clampLauncher(p: Pos): Pos {
  return {
    x: clampNum(p.x, 8, Math.max(8, window.innerWidth - SIZE - 8)),
    y: clampNum(p.y, 8, Math.max(8, window.innerHeight - SIZE - 8)),
  };
}

/** The resting place before anyone drags it: out of the way, bottom right. */
function defaultDock(): Dock {
  return { dx: MARGIN, dy: MARGIN, fromRight: true, fromBottom: true };
}

function toDock(p: Pos): Dock {
  const fromRight = p.x + SIZE / 2 > window.innerWidth / 2;
  const fromBottom = p.y + SIZE / 2 > window.innerHeight / 2;
  return {
    dx: fromRight ? window.innerWidth - p.x - SIZE : p.x,
    dy: fromBottom ? window.innerHeight - p.y - SIZE : p.y,
    fromRight,
    fromBottom,
  };
}

function toPos(d: Dock): Pos {
  return clampLauncher({
    x: d.fromRight ? window.innerWidth - d.dx - SIZE : d.dx,
    y: d.fromBottom ? window.innerHeight - d.dy - SIZE : d.dy,
  });
}

function loadDock(): Dock {
  try {
    const raw = localStorage.getItem(POS_KEY);
    if (raw) {
      const saved = JSON.parse(raw) as Partial<Dock>;
      if (typeof saved.dx === "number" && typeof saved.dy === "number") {
        return {
          dx: saved.dx,
          dy: saved.dy,
          fromRight: !!saved.fromRight,
          fromBottom: !!saved.fromBottom,
        };
      }
    }
  } catch {
    /* ignore */
  }
  // Includes the older {x, y} format, which is discarded rather than migrated:
  // those coordinates are exactly the ones that do not survive a resize.
  return defaultDock();
}

export function ChatWidget() {
  const { pathname } = useLocation();
  const [dock, setDock] = useState<Dock>(loadDock);
  const [pos, setPos] = useState<Pos>(() => toPos(loadDock()));
  const [open, setOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem(OPEN_KEY) === "1";
    } catch {
      return false;
    }
  });

  // A question handed in by an "Ask AI" control elsewhere; the nonce makes each
  // one fire once. ChatPanel sends it when this changes.
  const [pending, setPending] = useState<{ text: string; nonce: number }>();

  const dragging = useRef(false);
  const moved = useRef(false);
  const start = useRef<Pos>({ x: 0, y: 0 });
  const offset = useRef<Pos>({ x: 0, y: 0 });

  useEffect(() => {
    const handler = (e: Event) => {
      const { query } = (e as CustomEvent<AskDetail>).detail;
      setOpen(true);
      if (query.trim()) setPending({ text: query, nonce: Date.now() });
    };
    window.addEventListener(ASK_EVENT, handler);
    return () => window.removeEventListener(ASK_EVENT, handler);
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(OPEN_KEY, open ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [open]);

  useEffect(() => {
    try {
      localStorage.setItem(POS_KEY, JSON.stringify(dock));
    } catch {
      /* ignore */
    }
  }, [dock]);

  // Re-derive the position from the docked edges, so the launcher returns to
  // its corner when the window grows again instead of sitting where a smaller
  // viewport had squeezed it.
  useEffect(() => {
    const onResize = () => setPos(toPos(dock));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [dock]);

  // The /ask page is itself the chat surface, so the floating dock is hidden
  // there to avoid two chat panels fighting over the same conversation.
  if (pathname === "/ask") return null;

  const onPointerDown = (e: React.PointerEvent) => {
    dragging.current = true;
    moved.current = false;
    start.current = { x: e.clientX, y: e.clientY };
    offset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y };
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    if (Math.hypot(e.clientX - start.current.x, e.clientY - start.current.y) > 5) {
      moved.current = true;
    }
    if (moved.current) {
      setPos(clampLauncher({ x: e.clientX - offset.current.x, y: e.clientY - offset.current.y }));
    }
  };
  const onPointerUp = () => {
    // A press that did not drag is a click: toggle the window.
    if (dragging.current && !moved.current) setOpen((v) => !v);
    // A real drag re-docks the launcher to the edges it was dropped nearest.
    if (dragging.current && moved.current) setDock(toDock(pos));
    dragging.current = false;
  };

  // Window sized to fit the viewport, anchored near the launcher, on-screen.
  const winW = Math.min(WIN_W, window.innerWidth - 16);
  const winH = Math.min(WIN_H, window.innerHeight - 16);
  const winLeft = clampNum(pos.x + SIZE - winW, 8, Math.max(8, window.innerWidth - winW - 8));
  const winTop = clampNum(pos.y - winH - 12, 8, Math.max(8, window.innerHeight - winH - 8));

  return (
    <>
      {/* The window is always mounted (hidden when minimized) so a question in
          flight keeps thinking in the background and the conversation is not
          reset when the user minimizes. */}
      <div
        className={styles.window}
        style={{
          left: winLeft,
          top: winTop,
          width: winW,
          height: winH,
          display: open ? "flex" : "none",
        }}
        role="dialog"
        aria-label={`Ask ${PRODUCT_NAME}`}
        aria-hidden={!open}
      >
        <div className={styles.header}>
          <span className={styles.title}>Ask {PRODUCT_NAME}</span>
          <button
            type="button"
            className={styles.min}
            aria-label="Minimize chat"
            title="Minimize"
            onClick={() => setOpen(false)}
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 8h10" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className={styles.body}>
          <ChatPanel fill submitSignal={pending} visible={open} />
        </div>
      </div>

      <button
        type="button"
        className={styles.launcher}
        style={{ left: pos.x, top: pos.y }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        aria-label={open ? "Minimize assistant" : "Open assistant"}
        title="Ask ResearchSense — drag to move, click to open"
      >
        {open ? (
          <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
            <path d="M6 6l10 10M16 6L6 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H9l-4 3v-3H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"
              fill="currentColor"
            />
            <circle cx="8.5" cy="10.5" r="1.1" fill="var(--navy)" />
            <circle cx="12" cy="10.5" r="1.1" fill="var(--navy)" />
            <circle cx="15.5" cy="10.5" r="1.1" fill="var(--navy)" />
          </svg>
        )}
      </button>
    </>
  );
}
