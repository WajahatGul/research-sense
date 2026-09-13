import { useQuery } from "@tanstack/react-query";

import { fetchAnalytics } from "../api/analytics";
import { fetchStats } from "../api/stats";
import type { Stats } from "../types";
import { PageHeader } from "../components/PageHeader";
import { DataNote } from "../components/DataNote";
import { Loader, ErrorState } from "../components/StateViews";
import {
  CAMPUS_COLORS,
  CitationsTrend,
  DepartmentBars,
  InternationalTrend,
  PublicationsTrend,
  TopVenues,
} from "../features/analytics/charts";
import styles from "./Analytics.module.css";

/** What the charts below cover, in one sentence.
 *
 * Counts come from the live stats so a signed-in institution never reads the
 * demo deployment's totals. Built whole so it still reads correctly before
 * the counts arrive.
 */
function coverageNote(stats?: Stats): string {
  const scope = stats
    ? ` — ${stats.researchers.toLocaleString()} researcher` +
      `${stats.researchers === 1 ? "" : "s"} and ` +
      `${stats.publications.toLocaleString()} publication` +
      `${stats.publications === 1 ? "" : "s"}`
    : "";
  return (
    `These charts reflect only the data ResearchSense has indexed so far${scope}.` +
    " Real output is higher; coverage grows with each refresh."
  );
}

export default function Analytics() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics"],
    queryFn: fetchAnalytics,
  });
  // Coverage counts come from the same stats endpoint the home page uses, so
  // the note always matches the charts below it (and the signed-in workspace).
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });

  if (isLoading) return <Loader />;
  if (isError || !data) return <ErrorState />;

  // Degrade gracefully if the backend (e.g. an older deployed version) omits a
  // section — render what is present instead of crashing the whole page.
  const publicationsPerYear = data.publications_per_year ?? [];
  const campuses = data.campuses ?? [];
  const citationsPerYear = data.citations_per_year ?? [];
  const topVenues = data.top_venues ?? [];
  const campusTotals = data.campus_totals ?? [];
  const crossCampusPairs = data.cross_campus_pairs ?? [];
  const departmentTotals = data.department_totals ?? [];
  const internationalSplit = data.international_split ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Research intelligence"
        title="Analytics"
        description="Publication trends, citation growth, leading venues, and cross-campus collaboration, computed from the indexed research data."
      />

      <div className={`container ${styles.body}`}>
        <DataNote>{coverageNote(stats)}</DataNote>

        <section className={styles.card}>
          <h2 className={styles.h2}>Publications per year, by campus</h2>
          <PublicationsTrend
            data={publicationsPerYear}
            campuses={campuses}
          />
        </section>

        <div className={styles.twoCol}>
          <section className={styles.card}>
            <h2 className={styles.h2}>Citations earned by papers per year</h2>
            <CitationsTrend data={citationsPerYear} />
          </section>

          <section className={styles.card}>
            <h2 className={styles.h2}>Top publication venues</h2>
            <TopVenues data={topVenues} />
          </section>
        </div>

        <div className={styles.twoCol}>
          <section className={styles.card}>
            <h2 className={styles.h2}>Campus totals</h2>
            <div className={styles.tableWrap}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Campus</th>
                  <th>Researchers</th>
                  <th>Publications</th>
                  <th>Citations</th>
                </tr>
              </thead>
              <tbody>
                {campusTotals.map((row) => (
                  <tr key={row.campus}>
                    <td>
                      <span
                        className={styles.dot}
                        style={{ background: CAMPUS_COLORS[row.campus] }}
                      />
                      {row.campus}
                    </td>
                    <td className="mono">{row.researchers}</td>
                    <td className="mono">{row.publications}</td>
                    <td className="mono">{row.citations.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </section>

          <section className={styles.card}>
            <h2 className={styles.h2}>Cross-campus collaboration</h2>
            {crossCampusPairs.length === 0 ? (
              <p className={styles.empty}>
                No cross-campus co-authored papers found in the indexed data yet.
              </p>
            ) : (
              <ul className={styles.pairs}>
                {crossCampusPairs.map((pair) => (
                  <li key={`${pair.from}-${pair.to}`} className={styles.pair}>
                    <span className={styles.pairLabel}>
                      <span className={styles.campus}>
                        <span className={styles.dot}
                              style={{ background: CAMPUS_COLORS[pair.from] }} />
                        {pair.from}
                      </span>
                      <span className={styles.pairLink}>and</span>
                      <span className={styles.campus}>
                        <span className={styles.dot}
                              style={{ background: CAMPUS_COLORS[pair.to] }} />
                        {pair.to}
                      </span>
                    </span>
                    <span className="mono">
                      {pair.papers} joint {pair.papers === 1 ? "paper" : "papers"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className={styles.note}>
              Counted from papers whose author list includes researchers based
              at two or more campuses.
            </p>
          </section>
        </div>

        <div className={styles.twoCol}>
          <section className={styles.card}>
            <h2 className={styles.h2}>Publications by department</h2>
            {departmentTotals.length === 0 ? (
              <p className={styles.empty}>
                No department data found in the indexed data yet.
              </p>
            ) : (
              <DepartmentBars data={departmentTotals} />
            )}
          </section>

          <section className={styles.card}>
            <h2 className={styles.h2}>International vs domestic collaboration</h2>
            {internationalSplit.length === 0 ? (
              <p className={styles.empty}>
                No publication-year data found in the indexed data yet.
              </p>
            ) : (
              <InternationalTrend data={internationalSplit} />
            )}
          </section>
        </div>
      </div>
    </>
  );
}
