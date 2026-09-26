import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  CitationRow,
  DepartmentRow,
  IntlRow,
  VenueRow,
  YearRow,
} from "../../api/analytics";
import styles from "./charts.module.css";

// Fixed campus -> hue assignment (validated palette; color follows the
// entity, never the rank, so filtered views keep the same colors).
export const CAMPUS_COLORS: Record<string, string> = {
  "Islamabad (E-8)": "#3b6fd4",
  "Islamabad (H-11)": "#c9a227",
  Karachi: "#1f8a70",
  Lahore: "#9c4f96",
};

const INK = "#5b6472";
const GRID = "#e3e7ee";

const tooltipStyle = {
  fontSize: "0.82rem",
  borderRadius: 8,
  border: `1px solid ${GRID}`,
  boxShadow: "0 4px 14px rgba(6,24,58,0.08)",
};

export function PublicationsTrend({ data, campuses }: {
  data: YearRow[];
  campuses: string[];
}) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" tick={{ fill: INK, fontSize: 12 }}
               tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis tick={{ fill: INK, fontSize: 12 }} tickLine={false}
               axisLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: "0.82rem" }} />
        {campuses.map((campus) => (
          <Line
            key={campus}
            type="monotone"
            dataKey={campus}
            stroke={CAMPUS_COLORS[campus] ?? INK}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CitationsTrend({ data }: { data: CitationRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" tick={{ fill: INK, fontSize: 12 }}
               tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis tick={{ fill: INK, fontSize: 12 }} tickLine={false}
               axisLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Line type="monotone" dataKey="citations" stroke="#3b6fd4"
              strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function TopVenues({ data }: { data: VenueRow[] }) {
  return (
    <RankedBars
      label="Top publication venues"
      rows={data.slice(0, 8).map((r) => ({ name: r.venue, value: r.publications }))}
    />
  );
}

// Publications by department — top 10, one series, so no legend box — the
// section title names it.
export function DepartmentBars({ data }: { data: DepartmentRow[] }) {
  return (
    <RankedBars
      label="Publications by department"
      rows={data.slice(0, 10).map((r) => ({ name: r.department, value: r.publications }))}
    />
  );
}

/** A ranked list with bars drawn to one honest scale.
 *
 * These were SVG bar charts with a fixed 230 px label column. On a phone
 * the card is ~290 px wide, so the bars got the ~60 px left over and 228
 * papers looked almost the same as 81 — the picture misstated the data.
 * As HTML the name wraps above its bar on narrow screens, every bar is a
 * share of the largest value at any width, and screen readers read each
 * name with its number instead of an unlabelled drawing.
 */
function RankedBars({ rows, label }: { rows: { name: string; value: number }[]; label: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ol className={styles.ranked} aria-label={label}>
      {rows.map((r) => (
        <li key={r.name} className={styles.rankedRow}>
          <span className={styles.rankedName}>{r.name}</span>
          <span className={styles.rankedTrack} aria-hidden="true">
            <span
              className={styles.rankedBar}
              style={{ width: `${(r.value / max) * 100}%` }}
            />
          </span>
          <span className={`mono ${styles.rankedValue}`}>{r.value.toLocaleString()}</span>
        </li>
      ))}
    </ol>
  );
}

// International vs domestic collaboration — stacked bars per year.
// Entity-stable colors reused from the app's existing categorical slots
// (domestic = #3b6fd4, international = #1f8a70; validated pair, ΔE 18.5
// CVD / 19.4 normal-vision on a white surface).
export function InternationalTrend({ data }: { data: IntlRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="year" tick={{ fill: INK, fontSize: 12 }}
               tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis tick={{ fill: INK, fontSize: 12 }} tickLine={false}
               axisLine={false} allowDecimals={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Legend wrapperStyle={{ fontSize: "0.82rem" }} />
        <Bar dataKey="domestic" name="Domestic" stackId="a" fill="#3b6fd4"
             barSize={20} />
        <Bar dataKey="international" name="International" stackId="a"
             fill="#1f8a70" barSize={20} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
