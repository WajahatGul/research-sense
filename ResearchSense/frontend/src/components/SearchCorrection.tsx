import styles from "./SearchCorrection.module.css";

interface Props {
  /** What the visitor typed. */
  typed: string;
  /** The corrected query whose results are on screen. */
  shown: string;
}

/** Says plainly that results are for a corrected spelling, so a typo reads
 * as a typo rather than "this site has nothing about that". */
export function SearchCorrection({ typed, shown }: Props) {
  return (
    <p className={styles.note} role="status">
      No exact matches for <q>{typed}</q>. Showing results for{" "}
      <strong>
        <q>{shown}</q>
      </strong>
      .
    </p>
  );
}
