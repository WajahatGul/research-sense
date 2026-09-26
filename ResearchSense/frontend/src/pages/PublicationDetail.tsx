import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  fetchPublication,
  fetchRelatedPublications,
} from "../api/publications";
import { fetchTopics } from "../api/topics";
import { Badge } from "../components/Badge";
import { PageHeader } from "../components/PageHeader";
import { PublicationItem } from "../components/PublicationItem";
import { Section } from "../components/Section";
import { ErrorState, Loader } from "../components/StateViews";
import { askAssistant } from "../features/chat/askBus";
import { useOrganisation } from "../hooks/useOrganisation";
import { provenance } from "../lib/provenance";
import styles from "./PublicationDetail.module.css";

/** One paper as a destination.
 *
 * Papers had no page: a search hit, an assistant's source and a suggestion
 * could only re-run a title search or leave for the publisher's site. Here
 * the paper's authors lead to their profiles, its areas to the area pages,
 * and the papers to read next are listed under it.
 */
export default function PublicationDetail() {
  const { id } = useParams();
  const pubId = Number(id);
  const org = useOrganisation();

  const pub = useQuery({
    queryKey: ["publication", pubId],
    queryFn: () => fetchPublication(pubId),
    enabled: Number.isFinite(pubId),
  });
  const related = useQuery({
    queryKey: ["publication-related", pubId],
    queryFn: () => fetchRelatedPublications(pubId),
    enabled: pub.isSuccess,
  });
  // Area names on a paper link to the area's own page.
  const topics = useQuery({
    queryKey: ["topics", "", ""],
    queryFn: () => fetchTopics(),
  });

  if (pub.isLoading) return <Loader />;
  if (pub.error instanceof ApiError && pub.error.status === 404) {
    return (
      <div className={`container ${styles.missing}`}>
        <p>We don’t have a publication at this address.</p>
        <Link to="/publications">See all publications →</Link>
      </div>
    );
  }
  if (pub.isError || !pub.data) {
    return <ErrorState onRetry={() => pub.refetch()} />;
  }

  const p = pub.data;
  const typeLabel =
    org.document_types.find((t) => t.key === p.publication_type)?.label ??
    p.publication_type;
  const topicId = new Map(topics.data?.map((t) => [t.topic_name, t.topic_id]));
  const areas = p.topic_names?.length
    ? p.topic_names
    : p.topics.map((t) => t.topic_name);
  const origin = provenance(p.source);

  return (
    <>
      <PageHeader
        eyebrow={`${typeLabel} · ${p.publication_year}`}
        title={p.title}
      >
        <nav className={styles.crumbs} aria-label="Breadcrumb">
          <Link to="/publications">Publications</Link>
          <span aria-hidden="true"> / </span>
          <span aria-current="page">This paper</span>
        </nav>
        <p className={styles.authors}>
          {p.authors.map((a, i) => (
            <span key={`${a.full_name}-${i}`}>
              {i > 0 && ", "}
              {a.researcher_id ? (
                <Link to={`/researchers/${a.researcher_id}`}>
                  {a.full_name}
                </Link>
              ) : (
                a.full_name
              )}
            </span>
          ))}
        </p>
        <div className={styles.actions}>
          {p.doi && (
            <a
              className={styles.primary}
              href={`https://doi.org/${p.doi}`}
              target="_blank"
              rel="noreferrer"
            >
              Read at the publisher ↗
            </a>
          )}
          <button
            type="button"
            className={styles.secondary}
            onClick={() => askAssistant(`Tell me about the paper "${p.title}"`)}
          >
            Ask the assistant about this paper
          </button>
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        <div className={styles.column}>
          <dl className={styles.facts}>
            {p.journal_name && (
              <div>
                <dt>Published in</dt>
                <dd>{p.journal_name}</dd>
              </div>
            )}
            <div>
              <dt>Type</dt>
              <dd>{typeLabel}</dd>
            </div>
            <div>
              <dt>Cited</dt>
              <dd>
                <span className="mono">
                  {p.citation_count.toLocaleString()}
                </span>{" "}
                time{p.citation_count === 1 ? "" : "s"}
              </dd>
            </div>
            {p.campus && (
              <div>
                <dt>{org.site}</dt>
                <dd>{p.campus}</dd>
              </div>
            )}
            {p.doi && (
              <div>
                <dt>DOI</dt>
                <dd className={styles.doi}>{p.doi}</dd>
              </div>
            )}
            <div>
              <dt>Record from</dt>
              <dd title={origin.detail}>{origin.label.replace(/^via /, "")}</dd>
            </div>
          </dl>

          {p.abstract && (
            <section className={styles.abstract} aria-labelledby="abstract-h">
              <h2 id="abstract-h" className={styles.h2}>
                Abstract
              </h2>
              <p>{p.abstract}</p>
            </section>
          )}

          {areas.length > 0 && (
            <section aria-labelledby="areas-h">
              <h2 id="areas-h" className={styles.h2}>
                Research areas
              </h2>
              <div className={styles.areas}>
                {areas.map((name) => {
                  const tid = topicId.get(name);
                  return tid ? (
                    <Link
                      key={name}
                      to={`/topics/${tid}`}
                      className={styles.areaLink}
                    >
                      <Badge tone="gold">{name}</Badge>
                    </Link>
                  ) : (
                    <Badge key={name} tone="gold">
                      {name}
                    </Badge>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      </div>

      {related.data && related.data.length > 0 && (
        <Section eyebrow="Read next" title="Related papers">
          <div className={styles.related}>
            {related.data.map((r) => (
              <PublicationItem key={r.publication_id} pub={r} />
            ))}
          </div>
        </Section>
      )}
    </>
  );
}
