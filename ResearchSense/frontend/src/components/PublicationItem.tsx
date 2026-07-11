import { Link } from "react-router-dom";

import type { Publication } from "../types";
import { Badge } from "./Badge";
import styles from "./PublicationItem.module.css";

export function PublicationItem({ pub }: { pub: Publication }) {
  return (
    <article className={styles.item}>
      <div className={styles.year}>
        <span className="mono">{pub.publication_year}</span>
      </div>
      <div className={styles.body}>
        <h3 className={styles.title}>
          {pub.doi ? (
            <a
              href={`https://doi.org/${pub.doi}`}
              target="_blank"
              rel="noreferrer"
              className={styles.titleLink}
              title="Open the paper at its publisher (via DOI)"
            >
              {pub.title}
            </a>
          ) : (
            pub.title
          )}
        </h3>
        <p className={styles.authors}>
          {pub.authors.map((a) => a.full_name).join(", ")}
        </p>
        <div className={styles.meta}>
          <Badge tone={pub.publication_type === "journal" ? "navy" : "default"}>
            {pub.publication_type}
          </Badge>
          <span className={styles.journal}>{pub.journal_name}</span>
          <span className={styles.cites}>
            <span className="mono">{pub.citation_count}</span> citations
          </span>
          {pub.campus && <span className={styles.campus}>{pub.campus}</span>}
          <span className={styles.actions}>
            {pub.doi && (
              <a
                href={`https://doi.org/${pub.doi}`}
                target="_blank"
                rel="noreferrer"
                className={styles.action}
              >
                View paper ↗
              </a>
            )}
            <Link
              to={`/ask?q=${encodeURIComponent(
                `Tell me about the paper "${pub.title}"`)}`}
              className={styles.action}
            >
              Ask AI
            </Link>
          </span>
        </div>
      </div>
    </article>
  );
}
