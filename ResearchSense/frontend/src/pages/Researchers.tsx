import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";

import { fetchResearchers } from "../api/researchers";
import { PageHeader } from "../components/PageHeader";
import { SearchBar } from "../components/SearchBar";
import { ResearcherCard } from "../components/ResearcherCard";
import { Pagination } from "../components/Pagination";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import { FilterBar } from "../features/researchers/FilterBar";
import styles from "./Researchers.module.css";

const PAGE_SIZE = 12;

interface Filters {
  q: string;
  campus: string;
  department: string;
  designation: string;
}

export default function Researchers() {
  const [params, setParams] = useSearchParams();
  const initialQ = params.get("q") ?? "";

  const [pending, setPending] = useState<Filters>({
    q: initialQ,
    campus: "",
    department: "",
    designation: "",
  });
  // A deep-linked query (e.g. from a chat source chip) counts as an
  // implicit search, so it runs immediately instead of waiting for the button.
  const [applied, setApplied] = useState<Filters | null>(() =>
    initialQ ? { q: initialQ, campus: "", department: "", designation: "" } : null,
  );
  const [page, setPage] = useState(1);

  const hasSearched = applied !== null;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["researchers", applied, page],
    queryFn: () => {
      const f = applied ?? { q: "", campus: "", department: "", designation: "" };
      return fetchResearchers({
        q: f.q,
        campus: f.campus,
        department: f.department,
        designation: f.designation,
        page,
        page_size: PAGE_SIZE,
      });
    },
    enabled: hasSearched,
    placeholderData: keepPreviousData,
  });

  const setQuery = (value: string) => {
    setPending((p) => ({ ...p, q: value }));
    setParams(value ? { q: value } : {});
  };

  const runSearch = () => {
    setApplied(pending);
    setPage(1);
  };

  return (
    <>
      <PageHeader
        eyebrow="Directory"
        title="Researchers"
        description="Browse faculty across all campuses. Filter by campus, department, designation, or search by name and area."
      >
        <div className={styles.search}>
          <SearchBar
            placeholder="Search researchers…"
            defaultValue={pending.q}
            onSearch={setQuery}
          />
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        <FilterBar
          campus={pending.campus}
          department={pending.department}
          designation={pending.designation}
          total={data?.total ?? 0}
          hasSearched={hasSearched}
          onCampus={(v) => setPending((p) => ({ ...p, campus: v }))}
          onDepartment={(v) => setPending((p) => ({ ...p, department: v }))}
          onDesignation={(v) => setPending((p) => ({ ...p, designation: v }))}
          onSearch={runSearch}
        />

        {!hasSearched && (
          <EmptyState message="Choose your filters and press Search to see researchers." />
        )}
        {hasSearched && isLoading && <Loader />}
        {hasSearched && isError && <ErrorState />}
        {hasSearched && data && data.items.length === 0 && (
          <EmptyState message="No researchers match these filters yet." />
        )}
        {hasSearched && data && data.items.length > 0 && (
          <div className={styles.grid}>
            {data.items.map((r) => (
              <ResearcherCard key={r.researcher_id} researcher={r} />
            ))}
          </div>
        )}

        {hasSearched && data && (
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
