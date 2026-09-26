import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";

import { fetchPublications, fetchPublicationYears } from "../api/publications";
import { fetchCampuses, fetchDepartments } from "../api/researchers";
import { fetchStats } from "../api/stats";
import { fetchTopic } from "../api/topics";
import type { Stats } from "../types";
import { PageHeader } from "../components/PageHeader";
import { SearchBar } from "../components/SearchBar";
import { DataNote } from "../components/DataNote";
import { SearchCorrection } from "../components/SearchCorrection";
import { PublicationItem } from "../components/PublicationItem";
import { Pagination } from "../components/Pagination";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import { plural } from "../config";
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

const blankFilters: Filters = {
  q: "",
  year: "",
  campus: "",
  department: "",
  publicationType: "",
  dateFrom: "",
  dateTo: "",
};

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
  const [params] = useSearchParams();
  const topicId = params.get("topic_id");

  // Seed the search from the URL so other pages (e.g. chat source chips)
  // can deep-link straight to a title. The list starts with the newest
  // papers already showing: a catalogue that is blank until you press Search
  // looks empty, not ready.
  const initialQ = params.get("q") ?? "";
  const [pending, setPending] = useState<Filters>({ ...blankFilters, q: initialQ });
  const [applied, setApplied] = useState<Filters>(() => ({ ...blankFilters, q: initialQ }));
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);

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
    queryKey: ["publications", applied, topicId, page],
    queryFn: () => {
      const f = applied;
      return fetchPublications({
        q: f.q,
        year: f.year ? Number(f.year) : undefined,
        campus: f.campus || undefined,
        department: f.department || undefined,
        publication_type: f.publicationType
          ? (f.publicationType as "journal" | "conference")
          : undefined,
        date_from: f.dateFrom || undefined,
        date_to: f.dateTo || undefined,
        topic_id: topicId ? Number(topicId) : undefined,
        page,
        page_size: PAGE_SIZE,
      });
    },
    placeholderData: keepPreviousData,
  });

  const runSearch = (overrides?: Partial<Filters>) => {
    const next = overrides ? { ...pending, ...overrides } : pending;
    if (overrides) setPending(next);
    setApplied(next);
    setPage(1);
  };

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
        description="Journal articles and conference papers from researchers across all campuses."
      >
        <div className={styles.controls}>
          <div className={styles.search}>
            <SearchBar
              placeholder="Search publication titles…"
              suggest="publications"
              defaultValue={pending.q}
              onSearch={(v) => runSearch({ q: v })}
              hideButton
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
            value={pending.campus}
            onChange={(e) => setPending((p) => ({ ...p, campus: e.target.value }))}
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
            value={pending.year}
            onChange={(e) => setPending((p) => ({ ...p, year: e.target.value }))}
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
            value={pending.department}
            onChange={(e) => setPending((p) => ({ ...p, department: e.target.value }))}
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
            value={pending.publicationType}
            onChange={(e) =>
              setPending((p) => ({ ...p, publicationType: e.target.value }))
            }
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
                value={pending.dateFrom}
                onChange={(e) =>
                  setPending((p) => ({ ...p, dateFrom: e.target.value }))
                }
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
                value={pending.dateTo}
                onChange={(e) => setPending((p) => ({ ...p, dateTo: e.target.value }))}
                aria-label="To date"
              />
            </div>
          </div>
          </div>
          <button
            type="button"
            className={styles.searchButton}
            onClick={() => runSearch()}
            aria-label="Search publications"
          >
            Search
          </button>
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
            {(data?.total ?? 0).toLocaleString()} publications
          </span>
        )}

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
            onChange={setPage}
          />
        )}
      </div>
    </>
  );
}
