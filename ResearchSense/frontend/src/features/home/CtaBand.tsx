import { Link } from "react-router-dom";

import { askAssistant } from "../chat/askBus";
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
            Ask who works on a topic, what someone has published, or who could
            join a project. Answers come only from ResearchSense data and name
            their sources; if the data cannot answer, the assistant says so.
          </p>
        </div>
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.primary}
            onClick={() => askAssistant()}
          >
            Ask ResearchSense
          </button>
          <Link to="/collaboration" className={styles.secondary}>
            Collaboration finder
          </Link>
        </div>
      </div>
    </section>
  );
}
