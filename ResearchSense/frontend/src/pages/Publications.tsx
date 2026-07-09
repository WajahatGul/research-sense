import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";

import { fetchPublications, fetchPublicationYears } from "../api/publications";
import { PageHeader } from "../components/PageHeader";
import { SearchBar } from "../components/SearchBar";
import { PublicationItem } from "../components/PublicationItem";
import { Pagination } from "../components/Pagination";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import styles from "./Publications.module.css";

const PAGE_SIZE = 10;

export default function Publications() {
  const [params] = useSearchParams();
  const topicId = params.get("topic_id");

  const [q, setQ] = useState("");
  const [year, setYear] = useState("");
  const [page, setPage] = useState(1);

  const { data: years } = useQuery({
    queryKey: ["pub-years"],
    queryFn: fetchPublicationYears,
  });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["publications", q, year, topicId, page],
    queryFn: () =>
      fetchPublications({
        q,
        year: year ? Number(year) : undefined,
        topic_id: topicId ? Number(topicId) : undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        eyebrow="Research output"
        title="Publications"
        description="Journal articles and conference papers from Bahria University E-8 researchers."
      >
        <div className={styles.controls}>
          <div className={styles.search}>
            <SearchBar
              placeholder="Search publication titles…"
              onSearch={(v) => {
                setQ(v);
                setPage(1);
              }}
            />
          </div>
          <select
            className={styles.select}
            value={year}
            onChange={(e) => {
              setYear(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by year"
          >
            <option value="">All years</option>
            {years?.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        <span className={`mono ${styles.count}`}>
          {(data?.total ?? 0).toLocaleString()} publications
        </span>

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
