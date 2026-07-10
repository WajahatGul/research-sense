import { useQuery } from "@tanstack/react-query";

import { fetchAnalytics } from "../api/analytics";
import { PageHeader } from "../components/PageHeader";
import { Loader, ErrorState } from "../components/StateViews";
import {
  CAMPUS_COLORS,
  CitationsTrend,
  PublicationsTrend,
  TopVenues,
} from "../features/analytics/charts";
import styles from "./Analytics.module.css";

export default function Analytics() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["analytics"],
    queryFn: fetchAnalytics,
  });

  if (isLoading) return <Loader />;
  if (isError || !data) return <ErrorState />;

  return (
    <>
      <PageHeader
        eyebrow="Research intelligence"
        title="Analytics"
        description="Publication trends, citation growth, leading venues, and cross-campus collaboration, computed from the indexed research data."
      />

      <div className={`container ${styles.body}`}>
        <section className={styles.card}>
          <h2 className={styles.h2}>Publications per year, by campus</h2>
          <PublicationsTrend
            data={data.publications_per_year}
            campuses={data.campuses}
          />
        </section>

        <div className={styles.twoCol}>
          <section className={styles.card}>
            <h2 className={styles.h2}>Citations earned by papers per year</h2>
            <CitationsTrend data={data.citations_per_year} />
          </section>

          <section className={styles.card}>
            <h2 className={styles.h2}>Top publication venues</h2>
            <TopVenues data={data.top_venues} />
          </section>
        </div>

        <div className={styles.twoCol}>
          <section className={styles.card}>
            <h2 className={styles.h2}>Campus totals</h2>
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
                {data.campus_totals.map((row) => (
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
          </section>

          <section className={styles.card}>
            <h2 className={styles.h2}>Cross-campus collaboration</h2>
            {data.cross_campus_pairs.length === 0 ? (
              <p className={styles.empty}>
                No cross-campus co-authored papers found in the indexed data yet.
              </p>
            ) : (
              <ul className={styles.pairs}>
                {data.cross_campus_pairs.map((pair) => (
                  <li key={`${pair.from}-${pair.to}`} className={styles.pair}>
                    <span className={styles.pairLabel}>
                      <span className={styles.dot}
                            style={{ background: CAMPUS_COLORS[pair.from] }} />
                      {pair.from}
                      <span className={styles.pairLink}>and</span>
                      <span className={styles.dot}
                            style={{ background: CAMPUS_COLORS[pair.to] }} />
                      {pair.to}
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
      </div>
    </>
  );
}
