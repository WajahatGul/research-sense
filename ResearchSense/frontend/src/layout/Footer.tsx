import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchCampuses } from "../api/researchers";
import { Wordmark } from "../components/Wordmark";
import { useInstitution } from "../hooks/useInstitution";
import styles from "./Footer.module.css";

export default function Footer() {
  const institution = useInstitution();
  // Campuses come from the data being served, so a signed-in institution sees
  // its own sites rather than the demo deployment's.
  const { data: campuses } = useQuery({
    queryKey: ["campuses"],
    queryFn: fetchCampuses,
  });

  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.grid}`}>
        <div className={styles.brandCol}>
          <Wordmark light />
          <p className={styles.blurb}>
            A research information system {institution
              ? `for ${institution}`
              : "for universities"}. Profiles, publications, research areas and
            projects across all campuses in one place.
          </p>
        </div>

        <nav className={styles.col}>
          <span className={styles.head}>Explore</span>
          <Link to="/researchers">Researchers</Link>
          <Link to="/publications">Publications</Link>
          <Link to="/topics">Research Areas</Link>
          <Link to="/projects">Projects</Link>
        </nav>

        <nav className={styles.col}>
          <span className={styles.head}>Tools</span>
          <Link to="/guide">Get started</Link>
          <Link to="/collaboration">Collaboration finder</Link>
          <Link to="/library">Library</Link>
          <Link to="/ask">Ask ResearchSense</Link>
        </nav>

        {!!campuses?.length && (
          <div className={styles.col}>
            <span className={styles.head}>
              {campuses.length === 1 ? "Campus" : "Campuses"}
            </span>
            {campuses.map((c) => (
              <span key={c}>{c}</span>
            ))}
          </div>
        )}
      </div>

      <div className={`container ${styles.legal}`}>
        <span>© {new Date().getFullYear()} ResearchSense. Final Year Project.</span>
      </div>
    </footer>
  );
}
