import styles from "./Wordmark.module.css";

// Navy roundel with a gold compass-star, nodding to Bahria's naval heritage,
// paired with the ResearchSense wordmark and an E-8 campus subline.
export function Wordmark({ light = false }: { light?: boolean }) {
  return (
    <span className={`${styles.mark} ${light ? styles.light : ""}`}>
      <svg viewBox="0 0 40 40" className={styles.glyph} aria-hidden="true">
        <circle cx="20" cy="20" r="19" className={styles.disc} />
        <path
          d="M20 6 L23 17 L34 20 L23 23 L20 34 L17 23 L6 20 L17 17 Z"
          className={styles.star}
        />
        <circle cx="20" cy="20" r="2.4" className={styles.pivot} />
      </svg>
      <span className={styles.text}>
        <span className={styles.name}>ResearchSense</span>
        <span className={styles.sub}>Bahria University E-8</span>
      </span>
    </span>
  );
}
