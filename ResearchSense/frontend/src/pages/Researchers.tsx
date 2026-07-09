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

export default function Researchers() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";

  const [department, setDepartment] = useState("");
  const [designation, setDesignation] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["researchers", q, department, designation, page],
    queryFn: () =>
      fetchResearchers({
        q,
        department,
        designation,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const setQuery = (value: string) => {
    setPage(1);
    setParams(value ? { q: value } : {});
  };

  return (
    <>
      <PageHeader
        eyebrow="Directory"
        title="Researchers"
        description="Browse faculty of Bahria University, Islamabad E-8 campus. Filter by department, designation, or search by name and area."
      >
        <div className={styles.search}>
          <SearchBar
            placeholder="Search researchers…"
            defaultValue={q}
            onSearch={setQuery}
          />
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        <FilterBar
          department={department}
          designation={designation}
          total={data?.total ?? 0}
          onDepartment={(v) => {
            setDepartment(v);
            setPage(1);
          }}
          onDesignation={(v) => {
            setDesignation(v);
            setPage(1);
          }}
        />

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
            onChange={setPage}
          />
        )}
      </div>
    </>
  );
}
