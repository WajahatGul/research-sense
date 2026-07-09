import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { fetchProjects } from "../api/projects";
import { PageHeader } from "../components/PageHeader";
import { Badge } from "../components/Badge";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import styles from "./Projects.module.css";

const FILTERS = ["all", "ongoing", "completed"];

function formatPKR(amount: number): string {
  if (amount >= 1_000_000) return `PKR ${(amount / 1_000_000).toFixed(1)}M`;
  return `PKR ${amount.toLocaleString()}`;
}

export default function Projects() {
  const [status, setStatus] = useState("all");
  const { data, isLoading, isError } = useQuery({
    queryKey: ["projects", status],
    queryFn: () => fetchProjects(status === "all" ? undefined : status),
  });

  return (
    <>
      <PageHeader
        eyebrow="Funded research"
        title="Projects"
        description="Grant-funded research projects led by Bahria University E-8 faculty."
      >
        <div className={styles.tabs}>
          {FILTERS.map((f) => (
            <button
              key={f}
              className={`${styles.tab} ${status === f ? styles.tabActive : ""}`}
              onClick={() => setStatus(f)}
            >
              {f[0].toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        {isLoading && <Loader />}
        {isError && <ErrorState />}
        {data && data.length === 0 && (
          <EmptyState message="No projects in this category." />
        )}
        {data && data.length > 0 && (
          <div className={styles.grid}>
            {data.map((p) => (
              <article key={p.project_id} className={styles.card}>
                <div className={styles.cardHead}>
                  <Badge tone={p.status === "ongoing" ? "gold" : "default"}>
                    {p.status}
                  </Badge>
                  <span className={`mono ${styles.dates}`}>
                    {p.start_date.slice(0, 4)}–
                    {p.end_date ? p.end_date.slice(0, 4) : "…"}
                  </span>
                </div>
                <h3 className={styles.title}>{p.project_title}</h3>
                <p className={styles.desc}>{p.description}</p>
                <div className={styles.footer}>
                  <Link
                    to={`/researchers/${p.principal_investigator_id}`}
                    className={styles.pi}
                  >
                    {p.principal_investigator_name}
                  </Link>
                  {p.funding.map((f) => (
                    <div key={f.funding_id} className={styles.fund}>
                      <span className={styles.agency}>{f.agency_name}</span>
                      <span className={`mono ${styles.amount}`}>
                        {formatPKR(f.amount)}
                      </span>
                    </div>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
