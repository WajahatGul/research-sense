import { useQuery } from "@tanstack/react-query";

import { fetchStats } from "../../api/stats";
import { StatCard } from "../../components/StatCard";
import styles from "./StatsRow.module.css";

export function StatsRow() {
  const { data } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });

  // Only counts the data can back. The fourth card used to read "Funded
  // projects: 20", but those entries are illustrative samples with no
  // funding data — the Projects page says so itself. A false claim on the
  // front door costs more trust than an empty slot, so it counts
  // departments instead.
  const items = [
    { index: "01", label: "Researchers", value: data?.researchers, to: "/researchers" },
    { index: "02", label: "Publications", value: data?.publications, to: "/publications" },
    { index: "03", label: "Research areas", value: data?.topics, to: "/topics" },
    { index: "04", label: "Departments", value: data?.departments, to: "/analytics" },
  ];

  return (
    <div className={`container ${styles.wrap}`}>
      {items.map((it) => (
        <StatCard key={it.index} {...it} />
      ))}
    </div>
  );
}
