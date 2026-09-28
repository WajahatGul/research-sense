import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";

import { fetchPublications, fetchPublicationYears } from "../api/publications";
import { fetchCampuses, fetchDepartments } from "../api/researchers";
import { fetchStats } from "../api/stats";
import { fetchTopic } from "../api/topics";
import type { Stats } from "../types";
import { KeepSearch } from "../components/KeepSearch";
import { PageHeader } from "../components/PageHeader";
import { SearchBar } from "../components/SearchBar";
import { DataNote } from "../components/DataNote";
import { SearchCorrection } from "../components/SearchCorrection";
import { PublicationItem } from "../components/PublicationItem";
import { Pagination } from "../components/Pagination";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import { plural, pluralS } from "../config";
import { useOrganisation } from "../hooks/useOrganisation";
import styles from "./Publications.module.css";

const PAGE_SIZE = 10;

interface Filters {
  q: string;
  year: string;
  campus: string;
  department: string;
  publicationType: string;
  dateFrom: string;
  dateTo: string;
}

// Short, readable URL names for each filter: /publications?type=book&year=2023
const URL_KEYS: Record<keyof Filters, string> = {
  q: "q",
  year: "year",
  campus: "campus",
  department: "department",
  publicationType: "type",
  dateFrom: "from",
  dateTo: "to",
};

function filtersFrom(params: URLSearchParams): Filters {
  const f = {} as Filters;
  for (const [key, name] of Object.entries(URL_KEYS) as [keyof Filters, string][]) {
    f[key] = params.get(name) ?? "";
  }
  return f;
}

/** What this list covers, in one sentence.
 *
 * Read from the live stats: the count was hardcoded, so it kept claiming
 * 1,667 records after the corpus grew to 9,527, and told an institution
 * workspace the demo deployment's total.
 */
function coverageNote(stats?: Stats): string {
  const scope = stats
    ? ` — ${stats.publications.toLocaleString()} record` +
      `${stats.publications === 1 ? "" : "s"} matched from OpenAlex and` +
      " other sources"
    : "";
  return (
    `This list reflects only the publications ResearchSense has indexed so far${scope}.` +
    " Some papers are not yet included."
  );
}

export default function Publications() {
  const org = useOrganisation();
  const [params, setParams] = useSearchParams();
  const topicId = params.get("topic_id");

  // The URL is the record of what is being shown, as on Researchers and
  // Research areas. Filters used to live only in memory: opening a paper's
  // author and pressing Back dropped them all, and a filtered list could not
  // be shared or bookmarked. With no parameters the newest papers show: a
  // catalogue that is blank until you press Search looks empty, not ready.
  const applied = filtersFrom(params);
  const page = Math.max(Number(params.get("page")) || 1, 1);
  const urlKey = params.toString();

  const [filtersOpen, setFiltersOpen] = useState(false);

  const show = (f: Filters, p: number) => {
    const next = new URLSearchParams();
    for (const [key, name] of Object.entries(URL_KEYS) as [keyof Filters, string][]) {
      if (f[key]) next.set(name, f[key]);
    }
    if (topicId) next.set("topic_id", topicId);
    if (p > 1) next.set("page", String(p));
    setParams(next);
  };

  const { data: years } = useQuery({
    queryKey: ["pub-years"],
    queryFn: fetchPublicationYears,
  });
  const { data: campuses } = useQuery({
    queryKey: ["campuses"],
    queryFn: fetchCampuses,
  });
  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: fetchDepartments,
  });

  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });
  // Name the area a deep link filtered by, so the list explains itself.
  const { data: activeTopic } = useQuery({
    queryKey: ["topic", Number(topicId)],
    queryFn: () => fetchTopic(Number(topicId)),
    enabled: topicId != null,
  });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["publications", urlKey],
    queryFn: () => {
      const f = applied;
      return fetchPublications({
        q: f.q,
        year: f.year ? Number(f.year) : undefined,
        campus: f.campus || undefined,
        department: f.department || undefined,
        publication_type: f.publicationType || undefined,
        date_from: f.dateFrom || undefined,
        date_to: f.dateTo || undefined,
        topic_id: topicId ? Number(topicId) : undefined,
        page,
        page_size: PAGE_SIZE,
      });
    },
    placeholderData: keepPreviousData,
  });

  // A filter applies the moment it is chosen, as on Research areas. It used
  // to wait for a separate Search button, so choosing "2023" changed nothing
  // on screen until a second press, and the same control behaved one way
  // here and another way on the next page.
  const apply = (changes: Partial<Filters>) => show({ ...applied, ...changes }, 1);

  const activeFilters = [
    applied.campus,
    applied.year,
    applied.department,
    applied.publicationType,
    applied.dateFrom,
    applied.dateTo,
  ].filter(Boolean).length;

  return (
    <>
      <PageHeader
        eyebrow="Research output"
        title="Publications"
        description={`Articles, papers, chapters and books by the ${org.noun}'s researchers, newest first.`}
      >
        <div className={styles.controls}>
          <div className={styles.search}>
            <SearchBar
              key={applied.q}
              placeholder="Search publication titles…"
              suggest="publications"
              defaultValue={applied.q}
              onSearch={(v) => apply({ q: v })}
            />
          </div>
          {/* On a phone seven filter controls filled the whole first screen
              before a single result. There they fold behind one button that
              says how many are active; wider screens show them as before. */}
          <button
            type="button"
            className={styles.filterToggle}
            aria-expanded={filtersOpen}
            aria-controls="publication-filters"
            onClick={() => setFiltersOpen((v) => !v)}
          >
            {filtersOpen ? "Hide filters" : "Filters"}
            {activeFilters > 0 && ` · ${activeFilters} active`}
          </button>
          <div
            id="publication-filters"
            className={`${styles.filters} ${filtersOpen ? styles.filtersOpen : ""}`}
          >
          <select
            className={styles.select}
            value={applied.campus}
            onChange={(e) => apply({ campus: e.target.value })}
            aria-label={`Filter by ${org.site.toLowerCase()}`}
          >
            <option value="">All {plural(org.site).toLowerCase()}</option>
            {campuses?.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            className={styles.select}
            value={applied.year}
            onChange={(e) => apply({ year: e.target.value })}
            aria-label="Filter by year"
          >
            <option value="">All years</option>
            {years?.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
          <select
            className={styles.select}
            value={applied.department}
            onChange={(e) => apply({ department: e.target.value })}
            aria-label={`Filter by ${org.unit.toLowerCase()}`}
          >
            <option value="">All {plural(org.unit).toLowerCase()}</option>
            {departments?.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <select
            className={styles.select}
            value={applied.publicationType}
            onChange={(e) => apply({ publicationType: e.target.value })}
            aria-label="Filter by document type"
          >
            <option value="">All document types</option>
            {/* Only the types this organisation actually holds, with how
                many of each: journal and conference used to be hard-coded,
                which hid 229 book chapters and books entirely. */}
            {org.document_types.map((t) => (
              <option key={t.key} value={t.key}>
                {t.label} ({t.count.toLocaleString()})
              </option>
            ))}
          </select>
          <div className={styles.dateGroup}>
            <div className={styles.dateField}>
              <label className={styles.dateLabel} htmlFor="pub-date-from">
                From date
              </label>
              <input
                id="pub-date-from"
                type="date"
                className={styles.dateInput}
                value={applied.dateFrom}
                onChange={(e) => apply({ dateFrom: e.target.value })}
                aria-label="From date"
              />
            </div>
            <div className={styles.dateField}>
              <label className={styles.dateLabel} htmlFor="pub-date-to">
                To date
              </label>
              <input
                id="pub-date-to"
                type="date"
                className={styles.dateInput}
                value={applied.dateTo}
                onChange={(e) => apply({ dateTo: e.target.value })}
                aria-label="To date"
              />
            </div>
          </div>
          </div>
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        <DataNote>{coverageNote(stats)}</DataNote>

        {topicId && (
          <p className={styles.scope}>
            Showing publications in{" "}
            <Link to={`/topics/${topicId}`}>
              {activeTopic?.topic_name ?? "this research area"}
            </Link>
            . <Link to="/publications">Show all publications</Link>
          </p>
        )}

        {(
          <span className={`mono ${styles.count}`}>
            {(data?.total ?? 0).toLocaleString()} publication{pluralS(data?.total ?? 0)}
          </span>
        )}
        <KeepSearch
          key={urlKey}
          kind="publications"
          filters={{
            q: applied.q || undefined,
            year: applied.year || undefined,
            campus: applied.campus || undefined,
            department: applied.department || undefined,
            publication_type: applied.publicationType || undefined,
            date_from: applied.dateFrom || undefined,
            date_to: applied.dateTo || undefined,
            topic_id: topicId ?? undefined,
          }}
        />

        {data?.corrected_query && (
          <SearchCorrection typed={applied.q ?? ""} shown={data.corrected_query} />
        )}
        {isLoading && <Loader />}
        {isError && <ErrorState />}
        {data && data.items.length === 0 && (
          <EmptyState message="No publications match your search." />
        )}
        {data && data.items.length > 0 && (
          <div className={styles.list}>
            {data.items.map((p) => (
              <PublicationItem key={p.publication_id} pub={p} />
            ))}
          </div>
        )}

        {data && (
          <Pagination
            page={page}
            pageSize={PAGE_SIZE}
            total={data.total}
            onChange={(p) => show(applied, p)}
          />
        )}
      </div>
    </>
  );
}
