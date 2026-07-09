import styles from "./Pagination.module.css";

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onChange }: Props) {
  const pages = Math.max(Math.ceil(total / pageSize), 1);
  if (pages <= 1) return null;

  return (
    <nav className={styles.wrap} aria-label="Pagination">
      <button
        className={styles.btn}
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
      >
        ← Prev
      </button>
      <span className={`mono ${styles.status}`}>
        {page} / {pages}
      </span>
      <button
        className={styles.btn}
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        Next →
      </button>
    </nav>
  );
}
