import { Link } from "react-router-dom";

import styles from "./CtaBand.module.css";

export function CtaBand() {
  return (
    <section className={`container ${styles.wrap}`}>
      <div className={styles.band}>
        <div>
          <span className={styles.eyebrow}>Find your next collaborator</span>
          <h2 className={styles.title}>
            Ask in plain English. Discover who to work with.
          </h2>
          <p className={styles.lead}>
            ResearchSense links researchers by shared topics and answers
            questions about campus research — a preview of the assistant to come.
          </p>
        </div>
        <div className={styles.actions}>
          <Link to="/ask" className={styles.primary}>
            Ask ResearchSense
          </Link>
          <Link to="/collaboration" className={styles.secondary}>
            Collaboration finder
          </Link>
        </div>
      </div>
    </section>
  );
}
