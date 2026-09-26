import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { fetchPublications } from "../api/publications";
import { fetchResearchers } from "../api/researchers";
import { fetchTopic } from "../api/topics";
import { PageHeader } from "../components/PageHeader";
import { PublicationItem } from "../components/PublicationItem";
import { ResearcherCard } from "../components/ResearcherCard";
import { Section } from "../components/Section";
import { ErrorState, Loader } from "../components/StateViews";
import { askAssistant } from "../features/chat/askBus";
import styles from "./TopicDetail.module.css";

const PAPERS = 5;

/** A research area as a destination, not a filter.
 *
 * Area cards used to promise "N researchers" but only linked to a filtered
 * publication list, so the people — usually what a visitor wants — were
 * unreachable from the area. This page answers "who works on this, and
 * what have they published?" in one place.
 */
export default function TopicDetail() {
  const { id } = useParams();
  const topicId = Number(id);

  const topic = useQuery({
    queryKey: ["topic", topicId],
    queryFn: () => fetchTopic(topicId),
    enabled: Number.isFinite(topicId),
  });
  const people = useQuery({
    queryKey: ["topic-researchers", topicId],
    queryFn: () => fetchResearchers({ topic_id: topicId, page_size: 100 }),
    enabled: topic.isSuccess,
  });
  const papers = useQuery({
    queryKey: ["topic-publications", topicId],
    queryFn: () => fetchPublications({ topic_id: topicId, page_size: PAPERS }),
    enabled: topic.isSuccess,
  });

  if (topic.isLoading) return <Loader />;
  if (topic.error instanceof ApiError && topic.error.status === 404) {
    return (
      <div className={`container ${styles.missing}`}>
        <p>We don’t have a research area at this address.</p>
        <Link to="/topics">See all research areas →</Link>
      </div>
    );
  }
  if (topic.isError || !topic.data) {
    return <ErrorState onRetry={() => topic.refetch()} />;
  }

  const t = topic.data;
  const nPapers = papers.data?.total ?? t.publication_count;

  return (
    <>
      <PageHeader
        eyebrow="Research area"
        title={t.topic_name}
        description={`${t.researcher_count} researchers and ${t.publication_count} publications in ResearchSense are tagged with this area.`}
      >
        <nav className={styles.crumbs} aria-label="Breadcrumb">
          <Link to="/topics">Research areas</Link>
          <span aria-hidden="true"> / </span>
          <span aria-current="page">{t.topic_name}</span>
        </nav>
        <button
          type="button"
          className={styles.ask}
          onClick={() => askAssistant(`Who works on ${t.topic_name}?`)}
        >
          Ask the assistant about this area
        </button>
      </PageHeader>

      <Section eyebrow="People" title="Researchers in this area">
        {people.isLoading && <Loader />}
        {people.isError && <ErrorState onRetry={() => people.refetch()} />}
        {people.data && people.data.items.length === 0 && (
          <p className={styles.none}>
            No directory profile is tagged with this area yet. Its papers are
            listed below.
          </p>
        )}
        {people.data && people.data.items.length > 0 && (
          <div className={styles.people}>
            {people.data.items.map((r) => (
              <ResearcherCard key={r.researcher_id} researcher={r} />
            ))}
          </div>
        )}
      </Section>

      <Section
        eyebrow="Output"
        title="Recent publications"
        linkTo={nPapers > PAPERS ? `/publications?topic_id=${t.topic_id}` : undefined}
        linkLabel={`See all ${nPapers.toLocaleString()} publications`}
      >
        {papers.isLoading && <Loader />}
        {papers.isError && <ErrorState onRetry={() => papers.refetch()} />}
        {papers.data && papers.data.items.length > 0 && (
          <div className={styles.papers}>
            {papers.data.items.map((p) => (
              <PublicationItem key={p.publication_id} pub={p} />
            ))}
          </div>
        )}
      </Section>
    </>
  );
}
