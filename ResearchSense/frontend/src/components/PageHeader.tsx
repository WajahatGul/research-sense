import styles from "./PageHeader.module.css";

interface Props {
  eyebrow: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}

export function PageHeader({ eyebrow, title, description, children }: Props) {
  return (
    <header className={styles.header}>
      <div className="container">
        <span className="eyebrow">{eyebrow}</span>
        <h1 className={styles.title}>{title}</h1>
        {description && <p className={styles.desc}>{description}</p>}
        {children && <div className={styles.slot}>{children}</div>}
      </div>
    </header>
  );
}
