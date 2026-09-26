import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { fetchPublications } from "../api/publications";
import { fetchResearchers } from "../api/researchers";
import { fetchTopics } from "../api/topics";
import { PageHeader } from "../components/PageHeader";
import { PublicationItem } from "../components/PublicationItem";
import { ResearcherCard } from "../components/ResearcherCard";
import { SearchBar } from "../components/SearchBar";
import { SearchCorrection } from "../components/SearchCorrection";
import { Section } from "../components/Section";
import { ErrorState, Loader } from "../components/StateViews";
import { TopicCard } from "../components/TopicCard";
import { askAssistant } from "../features/chat/askBus";
import styles from "./Search.module.css";

const PEOPLE = 6;
const AREAS = 8;
const PAPERS = 5;

/** One place to answer "what do you have about X?".
 *
 * The home page invites a search for "a researcher, topic, or publication"
 * — so the results must actually cover all three, instead of sending every
 * query to the researcher directory where a paper title finds nobody.
 */
export default function Search() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const q = (params.get("q") ?? "").trim();

  const people = useQuery({
    queryKey: ["search", "researchers", q],
    queryFn: () => fetchResearchers({ q, page_size: PEOPLE }),
    enabled: q !== "",
  });
  const papers = useQuery({
    queryKey: ["search", "publications", q],
    queryFn: () => fetchPublications({ q, page_size: PAPERS }),
    enabled: q !== "",
  });
  // A corrected spelling applies to the whole search, so areas use it too.
  const corrected =
    people.data?.corrected_query ?? papers.data?.corrected_query ?? null;
  const effective = corrected ?? q;
  const areas = useQuery({
    queryKey: ["search", "topics", effective],
    queryFn: () => fetchTopics(effective),
    enabled: q !== "" && !people.isLoading && !papers.isLoading,
  });

  const loading = people.isLoading || papers.isLoading || areas.isLoading;
  const failed = people.isError && papers.isError;
  const nPeople = people.data?.total ?? 0;
  const nPapers = papers.data?.total ?? 0;
  const topicHits = areas.data ?? [];
  const nothing =
    q !== "" && !loading && !failed && nPeople + nPapers + topicHits.length === 0;
  const seeAll = encodeURIComponent(effective);

  return (
    <>
      <PageHeader
        eyebrow="Search"
        title={q ? `Results for “${q}”` : "Search ResearchSense"}
        description={
          q
            ? undefined
            : "Search researchers, research areas and publications in one go."
        }
      >
        <div className={styles.search}>
          <SearchBar
            key={q}
            size="lg"
            suggest="all"
            defaultValue={q}
            placeholder="A name, a research area, or words from a paper title…"
            onSearch={(v) =>
              navigate(v ? `/search?q=${encodeURIComponent(v)}` : "/search")
            }
          />
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        {corrected && <SearchCorrection typed={q} shown={corrected} />}
        {q && loading && <Loader label="Searching…" />}
        {q && failed && (
          <ErrorState onRetry={() => { people.refetch(); papers.refetch(); }} />
        )}

        {q && !loading && !failed && !nothing && (
          <nav className={styles.summary} aria-label="Result counts">
            <a href="#people">
              <strong className="mono">{nPeople.toLocaleString()}</strong>{" "}
              {nPeople === 1 ? "researcher" : "researchers"}
            </a>
            <a href="#areas">
              <strong className="mono">{topicHits.length.toLocaleString()}</strong>{" "}
              research {topicHits.length === 1 ? "area" : "areas"}
            </a>
            <a href="#papers">
              <strong className="mono">{nPapers.toLocaleString()}</strong>{" "}
              {nPapers === 1 ? "publication" : "publications"}
            </a>
          </nav>
        )}

        {nothing && (
          <div className={styles.empty}>
            <p className={styles.emptyTitle}>Nothing matches “{q}”.</p>
            <p className={styles.emptyText}>
              Try a single, broader word (a surname, or an area such as
              “energy”), browse the list of areas, or ask the assistant in
              plain English.
            </p>
            <div className={styles.emptyActions}>
              <Link to="/topics" className={styles.secondary}>
                Browse research areas
              </Link>
              <button
                type="button"
                className={styles.primary}
                onClick={() => askAssistant(q)}
              >
                Ask the assistant
              </button>
            </div>
          </div>
        )}
      </div>

      {!loading && nPeople > 0 && people.data && (
        <div id="people">
          <Section
            eyebrow="People"
            title="Researchers"
            linkTo={nPeople > PEOPLE ? `/researchers?q=${seeAll}` : undefined}
            linkLabel={`See all ${nPeople.toLocaleString()} researchers`}
          >
            <div className={styles.people}>
              {people.data.items.map((r) => (
                <ResearcherCard key={r.researcher_id} researcher={r} />
              ))}
            </div>
          </Section>
        </div>
      )}

      {!loading && topicHits.length > 0 && (
        <div id="areas">
          <Section eyebrow="Fields" title="Research areas">
            <div className={styles.areas}>
              {topicHits.slice(0, AREAS).map((t) => (
                <TopicCard key={t.topic_id} topic={t} />
              ))}
            </div>
          </Section>
        </div>
      )}

      {!loading && nPapers > 0 && papers.data && (
        <div id="papers">
          <Section
            eyebrow="Output"
            title="Publications"
            linkTo={nPapers > PAPERS ? `/publications?q=${seeAll}` : undefined}
            linkLabel={`See all ${nPapers.toLocaleString()} publications`}
          >
            <div className={styles.papers}>
              {papers.data.items.map((p) => (
                <PublicationItem key={p.publication_id} pub={p} />
              ))}
            </div>
          </Section>
        </div>
      )}
    </>
  );
}
