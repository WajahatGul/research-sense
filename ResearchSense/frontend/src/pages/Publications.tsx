import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";

import { fetchPublications, fetchPublicationYears } from "../api/publications";
import { fetchCampuses, fetchDepartments } from "../api/researchers";
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

  // Seed the search from the URL so other pages (e.g. chat source chips)
  // can deep-link straight to a title.
  const [q, setQ] = useState(params.get("q") ?? "");
  const [year, setYear] = useState("");
  const [campus, setCampus] = useState("");
  const [department, setDepartment] = useState("");
  const [publicationType, setPublicationType] = useState("");
  const [yearFrom, setYearFrom] = useState("");
  const [yearTo, setYearTo] = useState("");
  const [page, setPage] = useState(1);

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

  const { data, isLoading, isError } = useQuery({
    queryKey: [
      "publications",
      q,
      year,
      campus,
      department,
      publicationType,
      yearFrom,
      yearTo,
      topicId,
      page,
    ],
    queryFn: () =>
      fetchPublications({
        q,
        year: year ? Number(year) : undefined,
        campus: campus || undefined,
        department: department || undefined,
        publication_type: publicationType
          ? (publicationType as "journal" | "conference")
          : undefined,
        year_from: yearFrom ? Number(yearFrom) : undefined,
        year_to: yearTo ? Number(yearTo) : undefined,
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
        description="Journal articles and conference papers from researchers across all campuses."
      >
        <div className={styles.controls}>
          <div className={styles.search}>
            <SearchBar
              placeholder="Search publication titles…"
              defaultValue={q}
              onSearch={(v) => {
                setQ(v);
                setPage(1);
              }}
            />
          </div>
          <select
            className={styles.select}
            value={campus}
            onChange={(e) => {
              setCampus(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by campus"
          >
            <option value="">All campuses</option>
            {campuses?.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
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
          <select
            className={styles.select}
            value={department}
            onChange={(e) => {
              setDepartment(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by department"
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
            value={publicationType}
            onChange={(e) => {
              setPublicationType(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by paper type"
          >
            <option value="">All paper types</option>
            <option value="journal">Journal papers</option>
            <option value="conference">Conference papers</option>
          </select>
          <select
            className={styles.select}
            value={yearFrom}
            onChange={(e) => {
              setYearFrom(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by start year"
          >
            <option value="">From year</option>
            {years?.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
          <select
            className={styles.select}
            value={yearTo}
            onChange={(e) => {
              setYearTo(e.target.value);
              setPage(1);
            }}
            aria-label="Filter by end year"
          >
            <option value="">To year</option>
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
