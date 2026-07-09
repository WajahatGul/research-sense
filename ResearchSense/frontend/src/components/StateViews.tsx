import styles from "./StateViews.module.css";

export function Loader({ label = "Loading…" }: { label?: string }) {
  return (
    <div className={styles.state} role="status">
      <span className={styles.spinner} aria-hidden="true" />
      <span className={styles.text}>{label}</span>
    </div>
  );
}

export function ErrorState({ message }: { message?: string }) {
  return (
    <div className={styles.state}>
      <span className={styles.emoji}>⚠️</span>
      <p className={styles.text}>
        {message ?? "Could not reach the ResearchSense API."}
      </p>
      <p className={styles.hint}>
        Make sure the backend is running at{" "}
        <code className="mono">http://127.0.0.1:8000</code>.
      </p>
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
