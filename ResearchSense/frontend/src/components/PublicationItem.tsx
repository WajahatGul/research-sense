import { Link } from "react-router-dom";

import { askAssistant } from "../features/chat/askBus";

import type { Publication } from "../types";
import { provenance } from "../lib/provenance";
import { useOrganisation } from "../hooks/useOrganisation";
import { Badge } from "./Badge";
import { pluralS } from "../config";
import styles from "./PublicationItem.module.css";

export function PublicationItem({ pub }: { pub: Publication }) {
  const origin = provenance(pub.source);
  const { document_types } = useOrganisation();
  const typeLabel =
    document_types.find((t) => t.key === pub.publication_type)?.label ?? pub.publication_type;
  return (
    <article className={styles.item}>
      <div className={styles.year}>
        <span className="mono">{pub.publication_year}</span>
      </div>
      <div className={styles.body}>
        <h3 className={styles.title}>
          {/* The title opens the paper's own page (authors, areas, related
              papers); the publisher is one more press, under "View paper". */}
          <Link to={`/publications/${pub.publication_id}`} className={styles.titleLink}>
            {pub.title}
          </Link>
        </h3>
        <p className={styles.authors}>
          {pub.authors.map((a, i) => (
            <span key={`${a.full_name}-${i}`}>
              {i > 0 && ", "}
              {a.researcher_id ? (
                <Link to={`/researchers/${a.researcher_id}`} className={styles.authorLink}>
                  {a.full_name}
                </Link>
              ) : (
                a.full_name
              )}
            </span>
          ))}
        </p>
        <div className={styles.meta}>
          <Badge tone={pub.publication_type === "journal" ? "navy" : "default"}>
            {typeLabel}
          </Badge>
          <span className={styles.journal}>{pub.journal_name}</span>
          <span className={styles.cites}>
            <span className="mono">{pub.citation_count}</span> citation{pluralS(pub.citation_count)}
          </span>
          {pub.campus && <span className={styles.campus}>{pub.campus}</span>}
          <span className={styles.source} title={origin.detail}>
            {origin.label}
          </span>
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
            <button
              type="button"
              className={styles.action}
              onClick={() => askAssistant(`Tell me about the paper "${pub.title}"`)}
            >
              Ask AI
            </button>
          </span>
        </div>
      </div>
    </article>
  );
}
