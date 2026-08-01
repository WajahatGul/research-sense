import { useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchClaimedIds } from "../api/auth";
import { fetchResearcher } from "../api/researchers";
import { INSTITUTION_NAME } from "../config";
import { Avatar } from "../components/Avatar";
import { Badge } from "../components/Badge";
import { DataNote } from "../components/DataNote";
import { Loader, ErrorState } from "../components/StateViews";
import { coauthoredFirst } from "./coauthoredFirst";
import styles from "./ResearcherProfile.module.css";

const INTL_CAP = 10;

export default function ResearcherProfile() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const withParam = searchParams.get("with");
  const withId = withParam && !Number.isNaN(Number(withParam)) ? Number(withParam) : null;

  const [showAllIntl, setShowAllIntl] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["researcher", id],
    queryFn: () => fetchResearcher(Number(id)),
    enabled: Boolean(id),
  });
  const { data: claimedIds } = useQuery({
    queryKey: ["claimed-ids"],
    queryFn: fetchClaimedIds,
  });
  // Fetch the origin researcher's name (for the "shown first" caption) only
  // when a valid `with` id is present. Degrade gracefully — no caption — if
  // this fetch fails or the id doesn't resolve to a real researcher.
  const { data: withResearcher, isError: withError } = useQuery({
    queryKey: ["researcher", withId],
    queryFn: () => fetchResearcher(withId as number),
    enabled: withId != null,
    retry: false,
  });
  const isClaimed = Boolean(data && claimedIds?.includes(data.researcher_id));

  if (isLoading) return <Loader />;
  if (isError || !data) return <ErrorState message="Researcher not found." />;

  const showCaption = withId != null && !withError && Boolean(withResearcher);
  const orderedPublications = showCaption
    ? coauthoredFirst(data.publications, data.researcher_id, withId)
    : data.publications;

  const intlVisible = showAllIntl
    ? data.international_collaborations
    : data.international_collaborations.slice(0, INTL_CAP);
  const intlRemaining = data.international_collaborations.length - INTL_CAP;

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
              {INSTITUTION_NAME ? `${INSTITUTION_NAME}, ` : ""}{data.campus} campus
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
            <DataNote>
              Publication and citation counts reflect only what ResearchSense
              has indexed so far and may understate this researcher's full
              output.
            </DataNote>
            {showCaption && (
              <p className={styles.coauthorCaption}>
                Papers co-authored with {withResearcher?.full_name} shown first.
              </p>
            )}
            <ul className={styles.pubs}>
              {orderedPublications.map((p) => (
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
              {orderedPublications.length === 0 && (
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

          {data.international_collaborations.length > 0 && (
            <div className={styles.card}>
              <h3 className={styles.h3}>International collaborations</h3>
              <ul className={styles.intlList}>
                {intlVisible.map((c, i) => (
                  <li key={`${c.institution}-${i}`} className={styles.intlItem}>
                    {c.institution} · {c.country}
                  </li>
                ))}
              </ul>
              {intlRemaining > 0 && (
                <button
                  type="button"
                  className={styles.intlMore}
                  onClick={() => setShowAllIntl((v) => !v)}
                >
                  {showAllIntl ? "Show fewer" : `+${intlRemaining} more`}
                </button>
              )}
            </div>
          )}

          <div className={styles.card}>
            <h3 className={styles.h3}>Suggested collaborators</h3>
            <ul className={styles.collabs}>
              {data.collaborators.map((c) => (
                <li key={c.researcher_id}>
                  <Link
                    to={`/researchers/${c.researcher_id}?with=${data.researcher_id}`}
                    className={styles.collab}
                  >
                    <span className={styles.collabName}>{c.full_name}</span>
                    <span className={styles.collabMeta}>{c.designation}</span>
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
