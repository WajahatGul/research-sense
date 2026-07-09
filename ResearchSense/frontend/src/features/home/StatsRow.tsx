import { useQuery } from "@tanstack/react-query";

import { fetchStats } from "../../api/stats";
import { StatCard } from "../../components/StatCard";
import styles from "./StatsRow.module.css";

export function StatsRow() {
  const { data } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });

  const items = [
    { index: "01", label: "Researchers", value: data?.researchers ?? 0 },
    { index: "02", label: "Publications", value: data?.publications ?? 0 },
    { index: "03", label: "Research areas", value: data?.topics ?? 0 },
    { index: "04", label: "Funded projects", value: data?.projects ?? 0 },
  ];

  return (
    <div className={`container ${styles.wrap}`}>
      {items.map((it) => (
        <StatCard key={it.index} {...it} />
      ))}
    </div>
  );
}
