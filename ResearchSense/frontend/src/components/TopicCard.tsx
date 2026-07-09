import { Link } from "react-router-dom";

import type { Topic } from "../types";
import styles from "./TopicCard.module.css";

// The tile monogram encodes the area itself — first letters of the topic —
// keeping the "index / catalogue" language consistent across the portal.
function monogram(name: string): string {
  const words = name.split(/[\s-]+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function TopicCard({ topic }: { topic: Topic }) {
  return (
    <Link
      to={`/publications?topic_id=${topic.topic_id}`}
      className={styles.card}
    >
      <span className={styles.mono}>{monogram(topic.topic_name)}</span>
      <h3 className={styles.name}>{topic.topic_name}</h3>
      <p className={styles.meta}>
        <span className="mono">{topic.publication_count}</span> publications ·{" "}
        <span className="mono">{topic.researcher_count}</span> researchers
      </p>
    </Link>
  );
}
