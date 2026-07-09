import { Link } from "react-router-dom";

import type { Researcher } from "../types";
import { Avatar } from "./Avatar";
import { Badge } from "./Badge";
import styles from "./ResearcherCard.module.css";

export function ResearcherCard({ researcher }: { researcher: Researcher }) {
  const topics = researcher.topics.slice(0, 3);
  return (
    <Link to={`/researchers/${researcher.researcher_id}`} className={styles.card}>
      <div className={styles.top}>
        <Avatar name={researcher.full_name} />
        <div className={styles.head}>
          <h3 className={styles.name}>{researcher.full_name}</h3>
          <p className={styles.role}>{researcher.designation}</p>
          <p className={styles.campus}>
            {researcher.department} · {researcher.campus}
          </p>
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
