import { Link } from "react-router-dom";

import { Wordmark } from "../components/Wordmark";
import styles from "./Footer.module.css";

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={`container ${styles.grid}`}>
        <div className={styles.brandCol}>
          <Wordmark light />
          <p className={styles.blurb}>
            A research information system for Bahria University Islamabad,
            E-8 campus — profiles, publications, research areas and projects
            in one place.
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
          <Link to="/collaboration">Collaboration finder</Link>
          <Link to="/ask">Ask ResearchSense</Link>
        </nav>

        <div className={styles.col}>
          <span className={styles.head}>Campus</span>
          <span>Shangrila Road, Sector E-8</span>
          <span>Islamabad, Pakistan</span>
          <span className={styles.mono}>+92-51-9260002</span>
        </div>
      </div>

      <div className={`container ${styles.legal}`}>
        <span>© {new Date().getFullYear()} ResearchSense. Final Year Project.</span>
        <span className={styles.mono}>Data: Bahria University E-8</span>
      </div>
    </footer>
  );
}
