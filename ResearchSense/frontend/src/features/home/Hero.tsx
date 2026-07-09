import { useNavigate } from "react-router-dom";

import { SearchBar } from "../../components/SearchBar";
import styles from "./Hero.module.css";

export function Hero() {
  const navigate = useNavigate();

  return (
    <section className={styles.hero}>
      <div className={styles.grid} aria-hidden="true" />
      <div className={`container ${styles.inner}`}>
        <span className={styles.eyebrow}>Research Information System</span>
        <h1 className={styles.title}>
          The research of
          <span className={styles.accent}> Bahria University</span>
        </h1>
        <p className={styles.lead}>
          Search researchers, publications, and projects across every campus.
          One index for the people and ideas shaping our research.
        </p>

        <div className={styles.search}>
          <SearchBar
            size="lg"
            placeholder="Search a researcher, topic, or publication…"
            onSearch={(q) =>
              navigate(`/researchers${q ? `?q=${encodeURIComponent(q)}` : ""}`)
            }
          />
        </div>

        <div className={styles.suggest}>
          <span className={styles.suggestLabel}>Try</span>
          {["Machine Learning", "Cybersecurity", "Internet of Things"].map((t) => (
            <button
              key={t}
              className={styles.chip}
              onClick={() => navigate(`/researchers?q=${encodeURIComponent(t)}`)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
