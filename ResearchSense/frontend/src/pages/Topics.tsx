import { useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";

import { fetchTopics } from "../api/topics";
import { fetchDepartments } from "../api/researchers";
import type { Topic } from "../types";
import { PageHeader } from "../components/PageHeader";
import { SearchBar } from "../components/SearchBar";
import { TopicCard } from "../components/TopicCard";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import styles from "./Topics.module.css";

type Sort = "publications" | "researchers" | "name";

const SORTS: Record<Sort, { label: string; compare: (a: Topic, b: Topic) => number }> = {
  publications: {
    label: "Most publications",
    compare: (a, b) => b.publication_count - a.publication_count,
  },
  researchers: {
    label: "Most researchers",
    compare: (a, b) => b.researcher_count - a.researcher_count,
  },
  name: { label: "A to Z", compare: (a, b) => a.topic_name.localeCompare(b.topic_name) },
};

// 740 areas used to arrive as one wall of cards. A page of 48 is enough to
// scan; the rest are one press away, and search is the faster route anyway.
const STEP = 48;

export default function Topics() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const department = params.get("department") ?? "";
  const sortParam = params.get("sort") as Sort | null;
  const sort: Sort = sortParam && sortParam in SORTS ? sortParam : "publications";
  const shown = Math.max(Number(params.get("show")) || STEP, STEP);

  // The URL is the record of what is shown, as on the other lists: Back
  // from an area returns to the same search, filter and scroll depth.
  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v) next.set(k, v);
      else next.delete(k);
    }
    if (!("show" in changes)) next.delete("show");
    setParams(next, { replace: "show" in changes });
  };

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: fetchDepartments,
  });
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["topics", q, department],
    queryFn: () => fetchTopics(q, department),
    placeholderData: keepPreviousData,
  });

  // A search keeps its relevance order; browsing uses the chosen sort.
  const ordered = data ? (q ? data : [...data].sort(SORTS[sort].compare)) : [];
  const visible = ordered.slice(0, shown);
  const filtered = Boolean(q || department);

  return (
    <>
      <PageHeader
        eyebrow="Fields of inquiry"
        title="Research areas"
        description="The topics that organise research across the institution. Open an area to see who works on it and what they have published."
      >
        <div className={styles.search}>
          <SearchBar
            key={q}
            placeholder="Search research areas…"
            suggest="topics"
            defaultValue={q}
            onSearch={(v) => update({ q: v })}
          />
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        <div className={styles.bar}>
          <p className={styles.count} aria-live="polite">
            {data ? `${data.length.toLocaleString()} area${data.length === 1 ? "" : "s"}` : " "}
          </p>
          <div className={styles.controls}>
            <select
              className={styles.select}
              aria-label="Filter by department"
              value={department}
              onChange={(e) => update({ department: e.target.value })}
            >
              <option value="">All departments</option>
              {departments?.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <select
              className={styles.select}
              aria-label="Sort areas"
              value={q ? "relevance" : sort}
              disabled={Boolean(q)}
              onChange={(e) => update({ sort: e.target.value === "publications" ? "" : e.target.value })}
            >
              {q && <option value="relevance">Best match</option>}
              {(Object.keys(SORTS) as Sort[]).map((s) => (
                <option key={s} value={s}>
                  {SORTS[s].label}
                </option>
              ))}
            </select>
            {filtered && (
              <button
                type="button"
                className={styles.clear}
                onClick={() => update({ q: "", department: "" })}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {isLoading && <Loader />}
        {isError && <ErrorState onRetry={() => refetch()} />}
        {data && data.length === 0 && (
          <EmptyState
            message={
              q
                ? `No research area matches “${q}”${department ? ` in ${department}` : ""}.`
                : "No research areas are listed for this department yet."
            }
          />
        )}
        {visible.length > 0 && (
          <div className={styles.grid}>
            {visible.map((t) => (
              <TopicCard key={t.topic_id} topic={t} />
            ))}
          </div>
        )}
        {ordered.length > shown && (
          <div className={styles.moreRow}>
            <button
              type="button"
              className={styles.more}
              onClick={() => update({ show: String(shown + STEP) })}
            >
              Show {Math.min(STEP, ordered.length - shown)} more
            </button>
            <span className={styles.moreNote}>
              {shown} of {ordered.length.toLocaleString()} shown
            </span>
          </div>
        )}
      </div>
    </>
  );
}
