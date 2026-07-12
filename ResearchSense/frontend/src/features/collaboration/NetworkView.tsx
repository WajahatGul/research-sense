import { Link } from "react-router-dom";

import type { CollaborationSuggestion } from "../../types";
import styles from "./NetworkView.module.css";

interface Props {
  centerName: string;
  collaborators: CollaborationSuggestion[];
}

function shortName(name: string): string {
  return name.replace(/^(Dr\.|Mr\.|Ms\.|Mrs\.|Prof\.|Engr\.)\s*/i, "");
}

function initials(name: string): string {
  return shortName(name)
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

// Radial graph: the selected researcher at the centre; suggested collaborators
// around them. Link thickness and node ring encode the NUMBER of shared
// research areas (the honest signal), and each suggestion lists the actual
// shared areas so the recommendation is explainable.
export function NetworkView({ centerName, collaborators }: Props) {
  const size = 460;
  const c = size / 2;
  const radius = 165;
  const nodes = collaborators.slice(0, 6);
  const maxShared = Math.max(1, ...nodes.map((n) => n.shared_count));

  const pos = (i: number) => {
    const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
    return { x: c + radius * Math.cos(angle), y: c + radius * Math.sin(angle) };
  };

  return (
    <div className={styles.wrap}>
      <svg viewBox={`0 0 ${size} ${size}`} className={styles.svg}>
        {nodes.map((n, i) => {
          const { x, y } = pos(i);
          // Past co-authors get the strongest link; otherwise strength tracks
          // the number of shared research areas.
          const strength = n.past_coauthor ? 1 : n.shared_count / maxShared;
          return (
            <line
              key={`l-${n.researcher_id}`}
              x1={c}
              y1={c}
              x2={x}
              y2={y}
              stroke="var(--gold)"
              strokeWidth={1.5 + strength * 5}
              opacity={0.3 + strength * 0.55}
            />
          );
        })}

        {nodes.map((n, i) => {
          const { x, y } = pos(i);
          const cls = n.past_coauthor
            ? styles.nodeCoauthor
            : n.same_campus
              ? styles.node
              : styles.nodeCross;
          const initCls = n.past_coauthor ? styles.nodeInitCo : styles.nodeInit;
          return (
            <g key={n.researcher_id}>
              <circle cx={x} cy={y} r={30} className={cls} />
              <text x={x} y={y - 41} className={styles.nodeLabel}>
                {shortName(n.full_name)}
              </text>
              <text x={x} y={y - 2} className={initCls}>
                {initials(n.full_name)}
              </text>
              <text
                x={x}
                y={y + 13}
                className={n.past_coauthor ? styles.nodeCountCo : styles.nodeCount}
              >
                {n.past_coauthor
                  ? `${n.copublications} paper${n.copublications === 1 ? "" : "s"}`
                  : `${n.shared_count} ${n.shared_count === 1 ? "area" : "areas"}`}
              </text>
            </g>
          );
        })}

        <circle cx={c} cy={c} r={46} className={styles.center} />
        <text x={c} y={c + 5} className={styles.centerLabel}>
          {initials(centerName)}
        </text>
      </svg>

      <div className={styles.side}>
        <p className={styles.sideHint}>
          Proven co-authors (filled gold) rank first, then the strongest
          shared-area matches.
        </p>
        <ul className={styles.legend}>
          {nodes.map((n) => (
            <li key={n.researcher_id}>
              <Link
                to={`/researchers/${n.researcher_id}`}
                className={styles.legendItem}
              >
                <span className={styles.legendTop}>
                  <span className={styles.legendName}>{n.full_name}</span>
                  <span className={styles.badges}>
                    {n.past_coauthor && (
                      <span className={styles.coBadge}>
                        {n.copublications} co-authored
                      </span>
                    )}
                    {!n.same_campus && (
                      <span className={styles.crossBadge}>cross-campus</span>
                    )}
                  </span>
                </span>
                <span className={styles.legendRole}>
                  {n.designation}
                  {n.campus ? ` · ${n.campus}` : ""}
                </span>
                {n.shared_topics.length > 0 && (
                  <span className={styles.chips}>
                    {n.shared_topics.map((t) => (
                      <span key={t} className={styles.chip}>
                        {t}
                      </span>
                    ))}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
