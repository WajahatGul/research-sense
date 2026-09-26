import { Link, useNavigate } from "react-router-dom";

import { INSTITUTION_NAME } from "../../config";
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
          {INSTITUTION_NAME ? (
            <>
              The research of
              <span className={styles.accent}> {INSTITUTION_NAME}</span>
            </>
          ) : (
            <>
              Discover research,
              <span className={styles.accent}> researchers, and ideas</span>
            </>
          )}
        </h1>
        <p className={styles.lead}>
          Find the right person, their research area, or a paper across every
          campus. One index for the people and ideas shaping our research.
        </p>

        <div className={styles.search}>
          <SearchBar
            size="lg"
            placeholder="A name, a research area, or words from a paper title…"
            onSearch={(q) =>
              navigate(q ? `/search?q=${encodeURIComponent(q)}` : "/researchers")
            }
          />
        </div>

        <div className={styles.suggest}>
          <span className={styles.suggestLabel}>Try</span>
          {["Machine Learning", "Cybersecurity", "Internet of Things"].map((t) => (
            <button
              key={t}
              className={styles.chip}
              onClick={() => navigate(`/search?q=${encodeURIComponent(t)}`)}
            >
              {t}
            </button>
          ))}
        </div>

        <p className={styles.newHere}>
          New here? <Link to="/guide">See what you can do with ResearchSense →</Link>
        </p>
      </div>
    </section>
  );
}
