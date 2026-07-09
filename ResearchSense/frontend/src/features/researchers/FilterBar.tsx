import { useQuery } from "@tanstack/react-query";

import {
  fetchCampuses,
  fetchDepartments,
  fetchDesignations,
} from "../../api/researchers";
import styles from "./FilterBar.module.css";

interface Props {
  campus: string;
  department: string;
  designation: string;
  onCampus: (v: string) => void;
  onDepartment: (v: string) => void;
  onDesignation: (v: string) => void;
  total: number;
}

export function FilterBar({
  campus,
  department,
  designation,
  onCampus,
  onDepartment,
  onDesignation,
  total,
}: Props) {
  const { data: campuses } = useQuery({
    queryKey: ["campuses"],
    queryFn: fetchCampuses,
  });
  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: fetchDepartments,
  });
  const { data: designations } = useQuery({
    queryKey: ["designations"],
    queryFn: fetchDesignations,
  });

  return (
    <div className={styles.bar}>
      <span className={`mono ${styles.count}`}>
        {total.toLocaleString()} researchers
      </span>
      <div className={styles.filters}>
        <select
          className={styles.select}
          value={campus}
          onChange={(e) => onCampus(e.target.value)}
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
          value={department}
          onChange={(e) => onDepartment(e.target.value)}
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
          value={designation}
          onChange={(e) => onDesignation(e.target.value)}
          aria-label="Filter by designation"
        >
          <option value="">All designations</option>
          {designations?.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
