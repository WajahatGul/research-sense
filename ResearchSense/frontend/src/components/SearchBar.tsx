import { useState } from "react";

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
}

export function SearchBar({
  placeholder = "Search…",
  defaultValue = "",
  onSearch,
  size = "md",
  hideButton = false,
}: Props) {
  const [value, setValue] = useState(defaultValue);

  return (
    <form
      className={`${styles.form} ${styles[size]}`}
      onSubmit={(e) => {
        e.preventDefault();
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
        onChange={(e) => setValue(e.target.value)}
        aria-label={placeholder}
      />
      {!hideButton && (
        <button type="submit" className={styles.button}>
          Search
        </button>
      )}
    </form>
  );
}
