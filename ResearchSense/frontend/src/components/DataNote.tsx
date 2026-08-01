import type { ReactNode } from "react";

import styles from "./DataNote.module.css";

interface Props {
  children: ReactNode;
}

/** A small muted note explaining that a page's data is a partial index,
 * not a complete or verified record. Reused across data-bearing pages. */
export function DataNote({ children }: Props) {
  return <p className={styles.note}>{children}</p>;
}
