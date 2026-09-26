import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  fetchAcademicRanks,
  fetchCampuses,
  fetchDepartments,
} from "../../api/researchers";
import { plural } from "../../config";
import { useOrganisation } from "../../hooks/useOrganisation";
import styles from "./FilterBar.module.css";

interface Props {
  campus: string;
  department: string;
  designation: string;
  onCampus: (v: string) => void;
  onDepartment: (v: string) => void;
  onDesignation: (v: string) => void;
  onSearch: () => void;
  total: number;
  hasSearched: boolean;
  /** Filters currently applied (from the URL), shown on the folded button. */
  activeCount?: number;
}

export function FilterBar({
  campus,
  department,
  designation,
  onCampus,
  onDepartment,
  onDesignation,
  onSearch,
  total,
  hasSearched,
  activeCount = 0,
}: Props) {
  const org = useOrganisation();
  // Phones fold the dropdowns behind one button, the same way the
  // publications page does, so both lists behave alike.
  const [open, setOpen] = useState(false);
  const { data: campuses } = useQuery({
    queryKey: ["campuses"],
    queryFn: fetchCampuses,
  });
  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: fetchDepartments,
  });
  const { data: academicRanks } = useQuery({
    queryKey: ["academic-ranks"],
    queryFn: fetchAcademicRanks,
  });

  return (
    <div className={styles.bar}>
      <span className={`mono ${styles.count}`}>
        {hasSearched ? `${total.toLocaleString()} researchers` : ""}
      </span>
      <div className={styles.filters}>
        <button
          type="button"
          className={styles.filterToggle}
          aria-expanded={open}
          aria-controls="researcher-filters"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Hide filters" : "Filters"}
          {activeCount > 0 && ` · ${activeCount} active`}
        </button>
        <div
          id="researcher-filters"
          className={`${styles.selects} ${open ? styles.selectsOpen : ""}`}
        >
        <select
          className={styles.select}
          value={campus}
          onChange={(e) => onCampus(e.target.value)}
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
          value={department}
          onChange={(e) => onDepartment(e.target.value)}
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
          value={designation}
          onChange={(e) => onDesignation(e.target.value)}
          aria-label="Filter by designation"
        >
          <option value="">All ranks</option>
          {academicRanks?.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        </div>
        <button
          type="button"
          className={styles.searchButton}
          onClick={onSearch}
          aria-label="Search researchers"
        >
          Search
        </button>
      </div>
    </div>
  );
}
