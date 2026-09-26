import styles from "./StateViews.module.css";

export function Loader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className={styles.state} role="status">
      <span className={styles.spinner} aria-hidden="true" />
      <span className={styles.text}>{label}</span>
    </div>
  );
}

interface ErrorProps {
  message?: string;
  /** Re-run the failed request. Without it, "Try again" reloads the page —
   * every failure still gets a way forward instead of a dead end. */
  onRetry?: () => void;
}

/** A failure a visitor can act on: what happened, that it is usually
 * temporary, and one obvious way to try again. (It used to tell the public
 * to "make sure the backend is running at 127.0.0.1:8000".) */
export function ErrorState({ message, onRetry }: ErrorProps) {
  return (
    <div className={styles.state} role="alert">
      <span className={styles.emoji} aria-hidden="true">
        ⚠️
      </span>
      <p className={styles.text}>{message ?? "We couldn’t load this just now."}</p>
      <p className={styles.hint}>
        This is usually temporary. Check your connection, then try again.
      </p>
      <button
        type="button"
        className={styles.retry}
        onClick={onRetry ?? (() => window.location.reload())}
      >
        Try again
      </button>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className={styles.state}>
      <span className={styles.emoji}>🔍</span>
      <p className={styles.text}>{message}</p>
    </div>
  );
}
