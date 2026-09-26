import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { fetchProjects } from "../api/projects";
import { fetchCampuses } from "../api/researchers";
import { PageHeader } from "../components/PageHeader";
import { DataNote } from "../components/DataNote";
import { Loader, ErrorState, EmptyState } from "../components/StateViews";
import { plural } from "../config";
import { useOrganisation, useTerms } from "../hooks/useOrganisation";
import styles from "./Projects.module.css";

export default function Projects() {
  const t = useTerms();
  const org = useOrganisation();
  const [campus, setCampus] = useState("");
  const { data: campuses } = useQuery({
    queryKey: ["campuses"],
    queryFn: fetchCampuses,
  });
  const { data, isLoading, isError } = useQuery({
    queryKey: ["projects", campus],
    queryFn: () => fetchProjects(undefined, campus || undefined),
  });

  return (
    <>
      <PageHeader
        eyebrow="Research directions"
        title="Projects"
        description={`Illustrative research directions led by ${t.people} across all ${t.sites}.`}
      >
        <div className={styles.controls}>
          <select
            className={styles.select}
            value={campus}
            onChange={(e) => setCampus(e.target.value)}
            aria-label={`Filter by ${org.site.toLowerCase()}`}
          >
            <option value="">All {plural(org.site).toLowerCase()}</option>
            {campuses?.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </PageHeader>

      <div className={`container ${styles.body}`}>
        <DataNote>
          Illustrative examples. There is no central feed of
          funded projects, so these entries pair a real person from the directory with
          one of their genuine research topics to demonstrate the page. They
          are not verified projects and carry no funding data.
        </DataNote>

        {isLoading && <Loader />}
        {isError && <ErrorState />}
        {data && data.length === 0 && (
          <EmptyState message="No projects in this category." />
        )}
        {data && data.length > 0 && (
          <div className={styles.grid}>
            {data.map((p) => (
              <article key={p.project_id} className={styles.card}>
                <h3 className={styles.title}>{p.project_title}</h3>
                <p className={styles.desc}>{p.description}</p>
                <div className={styles.footer}>
                  <Link
                    to={`/researchers/${p.principal_investigator_id}`}
                    className={styles.pi}
                  >
                    {p.principal_investigator_name}
                  </Link>
                  <span className={styles.campus}>
                    {p.department} · {p.campus}
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
