import { useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";

import { fetchResearchers } from "../api/researchers";
import { fetchStats } from "../api/stats";
import type { Stats } from "../types";
import { PageHeader } from "../components/PageHeader";
import { SearchBar } from "../components/SearchBar";
import { DataNote } from "../components/DataNote";
import { SearchCorrection } from "../components/SearchCorrection";
import { ResearcherCard } from "../components/ResearcherCard";
import { Pagination } from "../components/Pagination";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import { FilterBar } from "../features/researchers/FilterBar";
import { useOrganisation } from "../hooks/useOrganisation";
import styles from "./Researchers.module.css";

const PAGE_SIZE = 12;

interface Filters {
  q: string;
  campus: string;
  department: string;
  designation: string;
}

/** What the directory covers, in one sentence.
 *
 * The counts come from the live stats so the note can never contradict the
 * page (it used to claim a fixed "358 profiles across 22 departments" to an
 * institution holding one). Built as a whole sentence rather than inlined
 * fragments so it still reads correctly when the counts have not loaded.
 */
function coverageNote(stats?: Stats): string {
  const scope = stats
    ? ` — ${stats.researchers.toLocaleString()} profile` +
      `${stats.researchers === 1 ? "" : "s"} across ` +
      `${stats.departments} department${stats.departments === 1 ? "" : "s"}`
    : "";
  let note =
    "This directory lists the faculty profiles ResearchSense has full " +
    `details for${scope}.`;
  if (stats?.researchers_extended) {
    note +=
      ` A further ${stats.researchers_extended.toLocaleString()} authors have` +
      " published here without a directory profile — search their name above" +
      " to find their papers.";
  }
  return note;
}

const FILTER_KEYS = ["q", "campus", "department", "designation"] as const;

function filtersFrom(params: URLSearchParams): Filters {
  return {
    q: params.get("q") ?? "",
    campus: params.get("campus") ?? "",
    department: params.get("department") ?? "",
    designation: params.get("designation") ?? "",
  };
}

export default function Researchers() {
  const [params, setParams] = useSearchParams();
  const org = useOrganisation();

  // The URL is the record of what is being shown. Filtering, opening a
  // profile and pressing Back used to drop every filter and the page; now
  // Back, refresh and a shared link all return to the same list. With no
  // parameters the directory simply lists everyone, so "browse faculty"
  // works on arrival.
  const applied = filtersFrom(params);
  const page = Math.max(Number(params.get("page")) || 1, 1);


  const show = (f: Filters, p: number) => {
    const next = new URLSearchParams();
    for (const key of FILTER_KEYS) if (f[key]) next.set(key, f[key]);
    if (p > 1) next.set("page", String(p));
    setParams(next);
  };

  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });
  const { data, isLoading, isError } = useQuery({
    queryKey: ["researchers", applied, page],
    queryFn: () =>
      fetchResearchers({
        q: applied.q,
        campus: applied.campus,
        department: applied.department,
        designation: applied.designation,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  // A filter applies the moment it is chosen (see Publications).
  const apply = (changes: Partial<Filters>) => show({ ...applied, ...changes }, 1);

  return (
    <>
      <PageHeader
        eyebrow="Directory"
        title="Researchers"
        description={`Browse the people behind the ${org.noun}'s research. Filter by ${org.site.toLowerCase()}, ${org.unit.toLowerCase()} or rank, or search by name and area.`}
      >
        <div className={styles.search}>
          <SearchBar
            key={applied.q}
            placeholder="Search researchers…"
            suggest="researchers"
            defaultValue={applied.q}
            onSearch={(value) => apply({ q: value })}
          />
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        <FilterBar
          campus={applied.campus}
          department={applied.department}
          designation={applied.designation}
          total={data?.total ?? 0}
          hasSearched={true}
          activeCount={[applied.campus, applied.department, applied.designation].filter(Boolean).length}
          onCampus={(v) => apply({ campus: v })}
          onDepartment={(v) => apply({ department: v })}
          onDesignation={(v) => apply({ designation: v })}
        />

        <DataNote>
          {coverageNote(stats)}
        </DataNote>

        {data?.corrected_query && (
          <SearchCorrection typed={applied.q} shown={data.corrected_query} />
        )}
        {isLoading && <Loader />}
        {isError && <ErrorState />}
        {data && data.items.length === 0 && (
          <EmptyState message="No researchers match these filters yet." />
        )}
        {data && data.items.length > 0 && (
          <div className={styles.grid}>
            {data.items.map((r) => (
              <ResearcherCard key={r.researcher_id} researcher={r} />
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
