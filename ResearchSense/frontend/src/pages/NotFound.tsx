import { Link } from "react-router-dom";

import styles from "./NotFound.module.css";

export default function NotFound() {
  return (
    <div className={`container ${styles.wrap}`}>
      <span className={`mono ${styles.code}`}>404</span>
      <h1 className={styles.title}>Page not found</h1>
      <p className={styles.text}>
        That page isn’t part of the research index.
      </p>
      <Link to="/" className={styles.link}>
        ← Back to home
      </Link>
    </div>
  );
}
