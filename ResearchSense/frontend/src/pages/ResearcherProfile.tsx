import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchClaimedIds } from "../api/auth";
import { fetchResearcher } from "../api/researchers";
import { Avatar } from "../components/Avatar";
import { Badge } from "../components/Badge";
import { Loader, ErrorState } from "../components/StateViews";
import styles from "./ResearcherProfile.module.css";

export default function ResearcherProfile() {
  const { id } = useParams();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["researcher", id],
    queryFn: () => fetchResearcher(Number(id)),
    enabled: Boolean(id),
  });
  const { data: claimedIds } = useQuery({
    queryKey: ["claimed-ids"],
    queryFn: fetchClaimedIds,
  });
  const isClaimed = Boolean(data && claimedIds?.includes(data.researcher_id));

  if (isLoading) return <Loader />;
  if (isError || !data) return <ErrorState message="Researcher not found." />;

  return (
    <>
      <header className={styles.hero}>
        <div className={`container ${styles.heroInner}`}>
          <Avatar name={data.full_name} size={92} />
          <div>
            <span className="eyebrow">
              {data.department} · {data.campus}
            </span>
            <h1 className={styles.name}>
              {data.full_name}
              {isClaimed && (
                <span className={styles.claimed} title="This profile is managed by the researcher">
                  ✓ Claimed
                </span>
              )}
            </h1>
            <p className={styles.role}>{data.designation}</p>
            <p className={styles.inst}>
              {data.institution}, {data.campus} campus
            </p>
            <div className={styles.meta}>
              {data.email && (
                <a href={`mailto:${data.email}`} className={styles.metaItem}>
                  ✉ {data.email}
                </a>
              )}
              {data.orcid_id && (
                <span className={`mono ${styles.metaItem}`}>
                  ORCID {data.orcid_id}
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className={`container ${styles.grid}`}>
        <main className={styles.main}>
          <section>
            <h2 className={styles.h2}>Biography</h2>
            <p className={styles.bio}>{data.profile_bio}</p>
          </section>

          <section>
            <h2 className={styles.h2}>
              Publications{" "}
              <span className={`mono ${styles.badge}`}>
                {data.publications.length}
              </span>
            </h2>
            <ul className={styles.pubs}>
              {data.publications.map((p) => (
                <li key={p.publication_id} className={styles.pub}>
                  <span className={styles.pubTitle}>
                    {p.doi ? (
                      <a href={`https://doi.org/${p.doi}`} target="_blank"
                         rel="noreferrer" className={styles.pubLink}
                         title="Open the paper at its publisher (via DOI)">
                        {p.title}
                      </a>
                    ) : p.title}
                  </span>
                  <span className={styles.pubMeta}>
                    <span className="mono">{p.publication_year}</span> ·{" "}
                    {p.journal_name} ·{" "}
                    <span className="mono">{p.citation_count}</span> citations
                    {" · "}
                    {p.doi && (
                      <>
                        <a href={`https://doi.org/${p.doi}`} target="_blank"
                           rel="noreferrer" className={styles.pubAction}>
                          View paper ↗
                        </a>
                        {" · "}
                      </>
                    )}
                    <Link
                      to={`/ask?q=${encodeURIComponent(
                        `Tell me about the paper "${p.title}"`)}`}
                      className={styles.pubAction}
                    >
                      Ask AI
                    </Link>
                  </span>
                </li>
              ))}
              {data.publications.length === 0 && (
                <li className={styles.pubMeta}>No publications recorded yet.</li>
              )}
            </ul>
          </section>
        </main>

        <aside className={styles.aside}>
          <div className={styles.card}>
            <h3 className={styles.h3}>Research areas</h3>
            <div className={styles.topics}>
              {data.topics.map((t) => (
                <Badge key={t.topic_id} tone="gold">
                  {t.topic_name}
                </Badge>
              ))}
            </div>
          </div>

          {data.education && (
            <div className={styles.card}>
              <h3 className={styles.h3}>Education</h3>
              <p className={styles.education}>{data.education}</p>
            </div>
          )}

          <div className={styles.card}>
            <h3 className={styles.h3}>Suggested collaborators</h3>
            <ul className={styles.collabs}>
              {data.collaborators.map((c) => (
                <li key={c.researcher_id}>
                  <Link to={`/researchers/${c.researcher_id}`} className={styles.collab}>
                    <span className={styles.collabName}>{c.full_name}</span>
                    <span className={styles.collabMeta}>
                      {c.designation}
                      <span className={`mono ${styles.score}`}>
                        {(c.similarity_score * 100).toFixed(0)}%
                      </span>
                    </span>
                  </Link>
                </li>
              ))}
              {data.collaborators.length === 0 && (
                <li className={styles.collabMeta}>No suggestions yet.</li>
              )}
            </ul>
          </div>
        </aside>
      </div>
    </>
  );
}
