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

import type { CitationRow, VenueRow, YearRow } from "../../api/analytics";

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
  const rows = data.slice(0, 8);
  return (
    <ResponsiveContainer width="100%" height={rows.length * 42 + 30}>
      <BarChart data={rows} layout="vertical"
                margin={{ top: 0, right: 40, bottom: 0, left: 8 }}>
        <XAxis type="number" hide />
        <YAxis type="category" dataKey="venue" width={230}
               tick={{ fill: INK, fontSize: 12 }} tickLine={false}
               axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} />
        <Bar dataKey="publications" fill="#3b6fd4" barSize={14}
             radius={[0, 4, 4, 0]}
             label={{ position: "right", fill: INK, fontSize: 12 }} />
      </BarChart>
    </ResponsiveContainer>
  );
}
