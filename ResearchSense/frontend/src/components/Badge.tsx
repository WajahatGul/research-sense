import styles from "./Badge.module.css";

interface Props {
  children: React.ReactNode;
  tone?: "default" | "gold" | "navy";
}

export function Badge({ children, tone = "default" }: Props) {
  return <span className={`${styles.badge} ${styles[tone]}`}>{children}</span>;
}
