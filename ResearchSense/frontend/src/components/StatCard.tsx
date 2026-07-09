import { useCountUp } from "../hooks/useCountUp";
import styles from "./StatCard.module.css";

interface Props {
  value: number;
  label: string;
  index: string;
}

export function StatCard({ value, label, index }: Props) {
  const display = useCountUp(value);
  return (
    <div className={styles.card}>
      <span className={styles.index}>{index}</span>
      <span className={`mono ${styles.value}`}>{display.toLocaleString()}</span>
      <span className={styles.label}>{label}</span>
    </div>
  );
}
