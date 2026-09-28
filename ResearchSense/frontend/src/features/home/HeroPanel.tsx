import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchStats } from "../../api/stats";
import { fetchTopics } from "../../api/topics";
import { useTerms } from "../../hooks/useOrganisation";
import styles from "./Hero.module.css";

const FIELDS = 6;

/** What is inside, on the first screen.
 *
 * The right half of the hero was empty and the counts sat below the fold,
 * so a first visit showed a slogan and a box but no sign of what the portal
 * holds or where to begin. This panel answers both: live counts that open
 * their lists, and the largest fields for someone who would rather recognise
 * a subject than think of a search term. It is deliberately quieter than the
 * search box, which stays the one primary action on the screen.
 */
export function HeroPanel() {
  const t = useTerms();
  const { data: stats } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
  });
  const { data: topics } = useQuery({
    queryKey: ["topics", "", ""],
    queryFn: () => fetchTopics(),
  });

  const counts = [
    { label: "Researchers", value: stats?.researchers, to: "/researchers" },
    { label: "Publications", value: stats?.publications, to: "/publications" },
    { label: "Research areas", value: stats?.topics, to: "/topics" },
    {
      label: t.units.charAt(0).toUpperCase() + t.units.slice(1),
      value: stats?.departments,
      to: "/analytics",
    },
  ];

  const perField = new Map<string, number>();
  for (const topic of topics ?? []) {
    if (topic.field)
      perField.set(topic.field, (perField.get(topic.field) ?? 0) + 1);
  }
  const fields = [...perField.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, FIELDS);

  return (
    <aside className={styles.panel} aria-label="What is in ResearchSense">
      <ul className={styles.counts}>
        {counts.map((c) => (
          <li key={c.to}>
            <Link to={c.to} className={styles.count}>
              {c.value === undefined ? (
                <span
                  className={styles.countPending}
                  aria-label={`${c.label} loading`}
                />
              ) : (
                <span className={`mono ${styles.countValue}`}>
                  {c.value.toLocaleString()}
                </span>
              )}
              <span className={styles.countLabel}>{c.label}</span>
            </Link>
          </li>
        ))}
      </ul>

      {fields.length > 0 && (
        <div className={styles.fields}>
          <p className={styles.fieldsLabel}>Browse by field</p>
          <ul className={styles.fieldList}>
            {fields.map(([name, n]) => (
              <li key={name}>
                <Link
                  to={`/topics?field=${encodeURIComponent(name)}`}
                  className={styles.fieldLink}
                >
                  <span>{name}</span>
                  <span className={styles.fieldN}>{n}</span>
                </Link>
              </li>
            ))}
          </ul>
          <Link to="/topics" className={styles.allFields}>
            All {perField.size} fields →
          </Link>
        </div>
      )}
    </aside>
  );
}
