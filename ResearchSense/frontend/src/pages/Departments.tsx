import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { get } from "../api/client";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loader } from "../components/StateViews";
import { useTerms } from "../hooks/useOrganisation";
import styles from "./Departments.module.css";

interface Department {
  name: string;
  researchers: number;
  publications: number;
  campuses: string[];
  top_areas: string[];
}

const fetchDepartmentSummaries = () => get<Department[]>("/api/departments");

/** The organisation's units, as a way in.
 *
 * "22 Departments" on the home page opened Analytics, where departments are
 * one chart among many: a count that led nowhere useful. Many visitors think
 * in units ("who is in Computer Science?"), so each one here opens its
 * people, its papers and its research areas.
 */
export default function Departments() {
  const t = useTerms();
  const Units = t.units.charAt(0).toUpperCase() + t.units.slice(1);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["department-summaries"],
    queryFn: fetchDepartmentSummaries,
  });

  return (
    <>
      <PageHeader
        eyebrow="Directory"
        title={Units}
        description={`Every ${t.unit} with its people, its papers and what it mostly works on, largest first.`}
      />
      <div className={`container ${styles.body}`}>
        {isLoading && <Loader />}
        {isError && <ErrorState onRetry={() => refetch()} />}
        {data && (
          <ul className={styles.grid}>
            {data.map((d) => {
              const q = encodeURIComponent(d.name);
              return (
                <li key={d.name} className={styles.card}>
                  <h2 className={styles.name}>{d.name}</h2>
                  {d.campuses.length > 0 && (
                    <p className={styles.where}>{d.campuses.join(" · ")}</p>
                  )}
                  {d.top_areas.length > 0 && (
                    <p className={styles.areas}>Works on {d.top_areas.join(", ")}</p>
                  )}
                  <div className={styles.links}>
                    <Link to={`/researchers?department=${q}`}>
                      <span className="mono">{d.researchers}</span>{" "}
                      {d.researchers === 1 ? "person" : "people"}
                    </Link>
                    <Link to={`/publications?department=${q}`}>
                      <span className="mono">{d.publications.toLocaleString()}</span>{" "}
                      {d.publications === 1 ? "paper" : "papers"}
                    </Link>
                    <Link to={`/topics?department=${q}`}>Research areas</Link>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </>
  );
}
