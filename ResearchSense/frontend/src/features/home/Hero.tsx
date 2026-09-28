import { Link, useNavigate } from "react-router-dom";

import { useOrganisation } from "../../hooks/useOrganisation";
import { SearchBar } from "../../components/SearchBar";
import { HeroPanel } from "./HeroPanel";
import styles from "./Hero.module.css";

export function Hero() {
  const navigate = useNavigate();
  const org = useOrganisation();

  return (
    <section className={styles.hero}>
      <div className={styles.grid} aria-hidden="true" />
      <div className={`container ${styles.inner}`}>
        <div className={styles.main}>
          <span className={styles.eyebrow}>Research Information System</span>
          <h1 className={styles.title}>
            {org.name ? (
              <>
                The research of
                <span className={styles.accent}> {org.name}</span>
              </>
            ) : (
              <>
                Discover research,
                <span className={styles.accent}> researchers, and ideas</span>
              </>
            )}
          </h1>
          <p className={styles.lead}>
            Find the right person, their research area, or a document across
            every {org.site.toLowerCase()}. One index for the people and ideas
            shaping the {org.noun}'s research.
          </p>

          <div className={styles.search}>
            <SearchBar
              size="lg"
              suggest="all"
              placeholder="A name, a research area, or words from a paper title…"
              onSearch={(q) =>
                navigate(
                  q ? `/search?q=${encodeURIComponent(q)}` : "/researchers",
                )
              }
            />
          </div>

          <div className={styles.suggest}>
            <span className={styles.suggestLabel}>Try</span>
            {["Machine Learning", "Cybersecurity", "Internet of Things"].map(
              (t) => (
                <button
                  key={t}
                  className={styles.chip}
                  onClick={() => navigate(`/search?q=${encodeURIComponent(t)}`)}
                >
                  {t}
                </button>
              ),
            )}
          </div>

          <p className={styles.newHere}>
            New here?{" "}
            <Link to="/guide">See what you can do with ResearchSense →</Link>
          </p>
        </div>
        <HeroPanel />
      </div>
    </section>
  );
}
