import { Link } from "react-router-dom";

import styles from "./Section.module.css";

interface Props {
  eyebrow: string;
  title: string;
  linkTo?: string;
  linkLabel?: string;
  children: React.ReactNode;
}

export function Section({ eyebrow, title, linkTo, linkLabel, children }: Props) {
  return (
    <section className={`container ${styles.section}`}>
      <div className={styles.head}>
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2 className={styles.title}>{title}</h2>
        </div>
        {linkTo && (
          <Link to={linkTo} className={styles.link}>
            {linkLabel ?? "View all"} →
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}
