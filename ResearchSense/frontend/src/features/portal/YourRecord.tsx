import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  confirmSamePerson,
  dismissSuggestion,
  fetchMyCorrections,
  reportNotMine,
  type Correction,
} from "../../api/corrections";
import type { Publication } from "../../types";
import styles from "./portal.module.css";

function statusClass(status: Correction["status"]): string {
  if (status === "approved") return styles.statusApproved;
  if (status === "rejected") return styles.statusRejected;
  return styles.statusPending;
}

/** Your record, and the means to put it right.
 *
 * The data comes from matching printed names to people, which gets some
 * papers wrong and splits some people in two. The person who knows best is
 * the researcher, so they can say "this paper is not mine" and "that author
 * record is also me". Both go to an administrator, because they change what
 * everyone sees; the decision is then kept through every data refresh.
 */
export function YourRecord({ papers }: { papers: Publication[] }) {
  const queryClient = useQueryClient();
  const [disowning, setDisowning] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");

  const { data } = useQuery({
    queryKey: ["my-corrections"],
    queryFn: fetchMyCorrections,
  });
  const refresh = () =>
    queryClient.invalidateQueries({ queryKey: ["my-corrections"] });
  const fail = (e: unknown) =>
    setMessage(e instanceof Error ? e.message : "Something went wrong");

  const notMine = useMutation({
    mutationFn: ({ id, why }: { id: number; why: string }) =>
      reportNotMine(id, why),
    onSuccess: (res) => {
      setDisowning(null);
      setNote("");
      setMessage(res.message);
      void refresh();
    },
    onError: fail,
  });
  const same = useMutation({
    mutationFn: confirmSamePerson,
    onSuccess: (res) => {
      setMessage(res.message);
      void refresh();
    },
    onError: fail,
  });
  const dismiss = useMutation({
    mutationFn: dismissSuggestion,
    onSuccess: refresh,
    onError: fail,
  });
  const busy = notMine.isPending || same.isPending || dismiss.isPending;

  const pendingPapers = new Set(
    (data?.corrections ?? [])
      .filter((c) => c.kind === "not_author" && c.status === "pending")
      .map((c) => c.paper_title),
  );

  return (
    <>
      {message && (
        <p className={styles.status} role="status">
          {message}
        </p>
      )}

      {data && data.suggestions.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.h3}>Is this also you?</h3>
          <p className={styles.hint}>
            These author records carry a name like yours but are not on your
            profile. If one is you, its papers join your profile once an
            administrator confirms.
          </p>
          <ul className={styles.uploads}>
            {data.suggestions.map((s) => (
              <li key={s.openalex_id} className={styles.pendingItem}>
                <div className={styles.pendingHead}>
                  <span className={styles.pendingTitle}>{s.other_name}</span>
                  <span className={styles.pendingMeta}>
                    {s.paper_count} paper{s.paper_count === 1 ? "" : "s"}
                    {s.shared_coauthors > 0 &&
                      ` · ${s.shared_coauthors} co-author${s.shared_coauthors === 1 ? "" : "s"} in common`}
                  </span>
                </div>
                <ul className={styles.samplePapers}>
                  {s.papers.map((p) => (
                    <li key={p.publication_id}>
                      <Link
                        to={`/publications/${p.publication_id}`}
                        className={styles.link}
                      >
                        {p.title}
                      </Link>
                      {p.year && (
                        <span className={styles.uploadDate}> · {p.year}</span>
                      )}
                    </li>
                  ))}
                </ul>
                <div className={styles.pendingActions}>
                  <button
                    className={styles.primary}
                    disabled={busy}
                    onClick={() => same.mutate(s.openalex_id)}
                  >
                    Yes, this is me
                  </button>
                  <button
                    className={styles.secondary}
                    disabled={busy}
                    onClick={() => dismiss.mutate(s.openalex_id)}
                  >
                    No, not me
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={styles.section}>
        <h3 className={styles.h3}>Your publications</h3>
        <p className={styles.hint}>
          Papers linked to your profile. If one is not yours, say so and an
          administrator will remove it; it stays until then.
        </p>
        {papers.length === 0 ? (
          <p className={styles.hint}>No publications on your profile yet.</p>
        ) : (
          <ul className={styles.uploads}>
            {papers.map((p) => (
              <li key={p.publication_id} className={styles.pendingItem}>
                <div className={styles.pendingHead}>
                  <Link
                    to={`/publications/${p.publication_id}`}
                    className={styles.pendingTitle}
                  >
                    {p.title}
                  </Link>
                  <span className={`mono ${styles.uploadDate}`}>
                    {p.publication_year}
                  </span>
                  {pendingPapers.has(p.title) ? (
                    <span
                      className={`${styles.statusChip} ${styles.statusPending}`}
                    >
                      Removal requested
                    </span>
                  ) : (
                    disowning !== p.publication_id && (
                      <button
                        className={styles.textButton}
                        disabled={busy}
                        onClick={() => {
                          setDisowning(p.publication_id);
                          setNote("");
                        }}
                      >
                        Not mine
                      </button>
                    )
                  )}
                </div>
                {disowning === p.publication_id && (
                  <div className={styles.rejectRow}>
                    <input
                      className={styles.input}
                      placeholder="Optional: why (e.g. another person with my name)"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      disabled={busy}
                    />
                    <button
                      className={styles.secondary}
                      disabled={busy}
                      onClick={() =>
                        notMine.mutate({ id: p.publication_id, why: note })
                      }
                    >
                      Send for review
                    </button>
                    <button
                      className={styles.secondary}
                      disabled={busy}
                      onClick={() => setDisowning(null)}
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {data && data.corrections.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.h3}>Corrections you asked for</h3>
          <ul className={styles.uploads}>
            {data.corrections.map((c) => (
              <li key={c.id} className={styles.pendingItem}>
                <div className={styles.pendingHead}>
                  <span className={styles.pendingTitle}>
                    {c.kind === "not_author"
                      ? `Not mine: ${c.paper_title}`
                      : `Also me: ${c.other_name}`}
                  </span>
                  <span
                    className={`${styles.statusChip} ${statusClass(c.status)}`}
                  >
                    {c.status.charAt(0).toUpperCase() + c.status.slice(1)}
                  </span>
                </div>
                {c.status === "rejected" && c.review_note && (
                  <p className={styles.reviewNote}>
                    Reviewer note: {c.review_note}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
