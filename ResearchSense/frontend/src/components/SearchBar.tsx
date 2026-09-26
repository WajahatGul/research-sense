import { useEffect, useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchSuggestions, type Suggestion, type SuggestScope } from "../api/suggest";
import styles from "./SearchBar.module.css";

interface Props {
  placeholder?: string;
  defaultValue?: string;
  onSearch: (value: string) => void;
  size?: "lg" | "md";
  /** Hide the built-in submit button. The surrounding form still submits
   * (and calls onSearch) when Enter is pressed in the input. Used on pages
   * that have their own standalone Search button elsewhere in the filter
   * bar, so only one Search button is visible per page. */
  hideButton?: boolean;
  /** Show matches while typing. "all" mixes people, areas and papers;
   * a single scope keeps the list to what the page is about. Omit to turn
   * suggestions off. */
  suggest?: SuggestScope | "all";
}

const KIND_LABEL: Record<Suggestion["kind"], string> = {
  researcher: "Person",
  topic: "Area",
  publication: "Paper",
};

// Short enough to feel immediate, long enough not to fire on every letter
// of a word typed at speed.
const DEBOUNCE_MS = 150;
const MIN_CHARS = 2;

function useDebounced(value: string, ms: number): string {
  const [out, setOut] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setOut(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return out;
}

export function SearchBar({
  placeholder = "Search…",
  defaultValue = "",
  onSearch,
  size = "md",
  hideButton = false,
  suggest,
}: Props) {
  const navigate = useNavigate();
  const [value, setValue] = useState(defaultValue);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = useId();

  const typed = useDebounced(value.trim(), DEBOUNCE_MS);
  const enabled = Boolean(suggest) && open && typed.length >= MIN_CHARS;
  const { data } = useQuery({
    queryKey: ["suggest", suggest, typed],
    queryFn: () =>
      fetchSuggestions(typed, suggest === "all" ? undefined : suggest, suggest === "all" ? 3 : 6),
    enabled,
    staleTime: 60_000,
  });
  const items = enabled && data ? data : [];
  const showList = items.length > 0;

  const pick = (s: Suggestion) => {
    setOpen(false);
    setActive(-1);
    if (s.kind === "researcher") navigate(`/researchers/${s.id}`);
    else if (s.kind === "topic") navigate(`/topics/${s.id}`);
    else navigate(`/publications/${s.id}`);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showList) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => (i + 1) % items.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => (i <= 0 ? items.length - 1 : i - 1));
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      pick(items[active]);
    } else if (e.key === "Escape") {
      setOpen(false);
      setActive(-1);
    }
  };

  return (
    <div className={styles.wrap}>
      <form
        className={`${styles.form} ${styles[size]}`}
        onSubmit={(e) => {
          e.preventDefault();
          setOpen(false);
          onSearch(value.trim());
        }}
        role="search"
      >
        <svg viewBox="0 0 24 24" className={styles.icon} aria-hidden="true">
          <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" strokeWidth="2" />
          <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <input
          className={styles.input}
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            setValue(e.target.value);
            setOpen(true);
            setActive(-1);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          aria-label={placeholder}
          autoComplete="off"
          {...(suggest && {
            role: "combobox",
            "aria-autocomplete": "list" as const,
            "aria-expanded": showList,
            "aria-controls": listId,
            "aria-activedescendant": active >= 0 ? `${listId}-${active}` : undefined,
          })}
        />
        {!hideButton && (
          <button type="submit" className={styles.button}>
            Search
          </button>
        )}
      </form>
      {suggest && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Suggestions"
          className={styles.list}
          hidden={!showList}
        >
          {items.map((s, i) => (
            <li
              key={`${s.kind}-${s.id}`}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              className={`${styles.option} ${i === active ? styles.active : ""}`}
              // mousedown, not click: a click would blur the input first and
              // close the list before the choice registers.
              onMouseDown={(e) => {
                e.preventDefault();
                pick(s);
              }}
              onMouseEnter={() => setActive(i)}
            >
              {suggest === "all" && <span className={styles.kind}>{KIND_LABEL[s.kind]}</span>}
              <span className={styles.text}>
                <span className={styles.label}>{s.label}</span>
                {s.detail && <span className={styles.detail}>{s.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
