import { Link } from "react-router-dom";

import styles from "./StatCard.module.css";

interface Props {
  /** Undefined while loading — shown as a placeholder, never as 0. */
  value: number | undefined;
  label: string;
  index: string;
  /** Where the number leads: a count you can click through to the list. */
  to: string;
}

/** A headline count that is honest while loading and useful once loaded.
 *
 * It used to animate up from 0, so a slow API showed "0 Researchers" — a
 * false statement about the data — and the animation carried no
 * information. The number now appears as-is and links to what it counts.
 */
export function StatCard({ value, label, index, to }: Props) {
  const loading = value === undefined;
  return (
    <Link to={to} className={styles.card} aria-busy={loading}>
      <span className={styles.index}>{index}</span>
      {loading ? (
        <span className={styles.placeholder} aria-label={`${label} loading`} />
      ) : (
        <span className={`mono ${styles.value}`}>{value.toLocaleString()}</span>
      )}
      <span className={styles.label}>{label}</span>
    </Link>
  );
}
