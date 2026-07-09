import { Link } from "react-router-dom";

import type { CollaborationSuggestion } from "../../types";
import styles from "./NetworkView.module.css";

interface Props {
  centerName: string;
  collaborators: CollaborationSuggestion[];
}

// Radial graph: the selected researcher at the centre, suggested collaborators
// placed around them with link opacity encoding similarity strength.
export function NetworkView({ centerName, collaborators }: Props) {
  const size = 460;
  const c = size / 2;
  const radius = 168;
  const nodes = collaborators.slice(0, 6);

  return (
    <div className={styles.wrap}>
      <svg viewBox={`0 0 ${size} ${size}`} className={styles.svg}>
        {nodes.map((n, i) => {
          const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
          const x = c + radius * Math.cos(angle);
          const y = c + radius * Math.sin(angle);
          return (
            <line
              key={`l-${n.researcher_id}`}
              x1={c}
              y1={c}
              x2={x}
              y2={y}
              stroke="var(--gold)"
              strokeWidth={1 + n.similarity_score * 4}
              opacity={0.25 + n.similarity_score * 0.6}
            />
          );
        })}

        {nodes.map((n, i) => {
          const angle = (i / nodes.length) * Math.PI * 2 - Math.PI / 2;
          const x = c + radius * Math.cos(angle);
          const y = c + radius * Math.sin(angle);
          return (
            <g key={n.researcher_id}>
              <circle cx={x} cy={y} r={30} className={styles.node} />
              <text x={x} y={y - 40} className={styles.nodeLabel}>
                {n.full_name.replace(/^(Dr\.|Mr\.|Ms\.|Mrs\.)\s*/, "")}
              </text>
              <text x={x} y={y + 4} className={styles.score}>
                {(n.similarity_score * 100).toFixed(0)}%
              </text>
            </g>
          );
        })}

        <circle cx={c} cy={c} r={44} className={styles.center} />
        <text x={c} y={c + 4} className={styles.centerLabel}>
          {centerName
            .replace(/^(Dr\.|Mr\.|Ms\.|Mrs\.)\s*/, "")
            .split(" ")
            .map((w) => w[0])
            .join("")}
        </text>
      </svg>

      <ul className={styles.legend}>
        {nodes.map((n) => (
          <li key={n.researcher_id}>
            <Link to={`/researchers/${n.researcher_id}`} className={styles.legendItem}>
              <span className={styles.legendName}>{n.full_name}</span>
              <span className={styles.legendBasis}>{n.basis}</span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
