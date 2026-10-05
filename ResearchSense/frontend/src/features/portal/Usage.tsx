import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getToken } from "../../api/auth";
import { pluralS } from "../../config";
import styles from "./portal.module.css";

interface UsageSummary {
  days: number;
  visitors: number;
  returning_visitors: number;
  searches_without_results: number;
  top_missed_searches: { query: string; where: string; times: number }[];
  claims: { started: number; sent_for_review: number; profiles_claimed: number };
}

async function fetchUsage(days: number): Promise<UsageSummary> {
  const res = await fetch(`/api/admin/usage?days=${days}`, {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("Could not load usage");
  return res.json();
}

const pct = (part: number, whole: number) => (whole ? `${Math.round((100 * part) / whole)}%` : "–");

/** The few numbers that say whether the directory is working.
 *
 * Each points at something to do: a search that found nothing is a person,
 * paper or area to add (or a spelling to accept); claims started but not
 * sent mean the form is losing people; returning visitors show trust.
 * Counted without knowing who anyone is.
 */
export function Usage() {
  const [days, setDays] = useState(30);
  const { data } = useQuery({ queryKey: ["admin-usage", days], queryFn: () => fetchUsage(days) });

  return (
    <section className={styles.section}>
      <h3 className={styles.h3}>Usage</h3>
      <label className={styles.hint}>
        Last{" "}
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
        . Counted anonymously: no names, accounts or IP addresses.
      </label>
      {data && (
        <>
          <ul className={styles.usageFigures}>
            <li>
              <strong>{data.visitors}</strong> visitor{pluralS(data.visitors)},{" "}
              <strong>{data.returning_visitors}</strong> came back on another day (
              {pct(data.returning_visitors, data.visitors)})
            </li>
            <li>
              Profile claims: <strong>{data.claims.started}</strong> started,{" "}
              <strong>{data.claims.sent_for_review}</strong> sent for review,{" "}
              <strong>{data.claims.profiles_claimed}</strong> profile{pluralS(data.claims.profiles_claimed)} opened
            </li>
            <li>
              <strong>{data.searches_without_results}</strong>{" "}
              {data.searches_without_results === 1 ? "search" : "searches"} found nothing
            </li>
          </ul>
          {data.top_missed_searches.length > 0 && (
            <>
              <p className={styles.hint}>
                What people looked for and did not find. Each is someone or something to add,
                or a spelling the search should accept.
              </p>
              <ul className={styles.uploads}>
                {data.top_missed_searches.map((m) => (
                  <li key={`${m.where}:${m.query}`} className={styles.upload}>
                    <span>
                      “{m.query}”
                      <span className={styles.uploadDate}> · in {m.where}</span>
                    </span>
                    <span className={styles.uploadDate}>{m.times}×</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
