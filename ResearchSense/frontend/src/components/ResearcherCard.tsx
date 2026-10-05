import { Link } from "react-router-dom";

import type { Researcher } from "../types";
import { Avatar } from "./Avatar";
import { Badge } from "./Badge";
import styles from "./ResearcherCard.module.css";

export function ResearcherCard({ researcher }: { researcher: Researcher }) {
  const topics = researcher.topics.slice(0, 3);
  const placement = [researcher.department, researcher.campus].filter(Boolean).join(" · ");
  return (
    <Link to={`/researchers/${researcher.researcher_id}`} className={styles.card}>
      <div className={styles.top}>
        <Avatar name={researcher.full_name} />
        <div className={styles.head}>
          <h3 className={styles.name}>{researcher.full_name}</h3>
          {placement ? (
            <>
              <p className={styles.role}>{researcher.designation}</p>
              <p className={styles.campus}>{placement}</p>
            </>
          ) : (
            // Authors who appear on indexed papers but have no directory
            // entry used to show a lone "·" here, which read as broken data.
            <p className={styles.role}>Author on indexed papers · no directory profile</p>
          )}
        </div>
      </div>

      <div className={styles.topics}>
        {topics.map((t) => (
          <Badge key={t.topic_id}>{t.topic_name}</Badge>
        ))}
      </div>

      <div className={styles.stats}>
        <span>
          <b className="mono">{researcher.publication_count}</b> publications
        </span>
        <span>
          <b className="mono">{researcher.citation_count.toLocaleString()}</b> citations
        </span>
      </div>
    </Link>
  );
}
