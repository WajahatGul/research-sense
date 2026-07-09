import { useState } from "react";

import styles from "./SearchBar.module.css";

interface Props {
  placeholder?: string;
  defaultValue?: string;
  onSearch: (value: string) => void;
  size?: "lg" | "md";
}

export function SearchBar({
  placeholder = "Search…",
  defaultValue = "",
  onSearch,
  size = "md",
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
      <button type="submit" className={styles.button}>
        Search
      </button>
    </form>
  );
}
