import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  approveCorrection,
  decideCandidate,
  fetchIdentityCandidates,
  fetchPendingCorrections,
  rejectCorrection,
  type Correction,
  type Suggestion,
} from "../../api/corrections";
import styles from "./portal.module.css";

interface NotAuthorEvidence {
  printed_names: string[];
  journal: string | null;
  year: number | null;
}

function Evidence({ c }: { c: Correction }) {
  if (c.kind === "not_author") {
    const e = c.evidence as NotAuthorEvidence | undefined;
    return (
      <dl className={styles.evidence}>
        <dt>Paper</dt>
        <dd>
          {c.paper_title}
          {e?.year ? ` · ${e.year}` : ""}
          {e?.journal ? ` · ${e.journal}` : ""}
        </dd>
        <dt>Printed authors</dt>
        <dd>{e?.printed_names?.join(", ") || "—"}</dd>
        <dt>Their reason</dt>
        <dd>{c.note || "None given"}</dd>
      </dl>
    );
  }
  const e = c.evidence as Suggestion | undefined;
  return (
    <dl className={styles.evidence}>
      <dt>Other record</dt>
      <dd>
        {c.other_name} · {e?.paper_count ?? "?"} papers
      </dd>
      <dt>In common</dt>
      <dd>
        {e ? `${e.shared_coauthors} co-authors` : "—"}
        {e?.shared_areas?.length ? ` · ${e.shared_areas.join(", ")}` : ""}
      </dd>
      <dt>Their papers</dt>
      <dd>{e?.papers?.map((p) => p.title).join(" · ") || "—"}</dd>
    </dl>
  );
}

/** Record corrections waiting for a decision, and the system's own
 * "possibly the same person" suggestions, strongest evidence first. */
export function CorrectionsQueue() {
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const { data: pending } = useQuery({
    queryKey: ["admin-corrections"],
    queryFn: fetchPendingCorrections,
  });
  const { data: candidates } = useQuery({
    queryKey: ["admin-identity-candidates"],
    queryFn: () => fetchIdentityCandidates(10),
  });
  const done = () => {
    setRejecting(null);
    setNote("");
    setError("");
    void queryClient.invalidateQueries({ queryKey: ["admin-corrections"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-outbox"] });
    void queryClient.invalidateQueries({
      queryKey: ["admin-identity-candidates"],
    });
  };
  const fail = (e: unknown) =>
    setError(e instanceof Error ? e.message : "Could not update.");
  const approve = useMutation({
    mutationFn: approveCorrection,
    onSuccess: done,
    onError: fail,
  });
  const reject = useMutation({
    mutationFn: ({ id, why }: { id: number; why: string }) =>
      rejectCorrection(id, why),
    onSuccess: done,
    onError: fail,
  });
  const decide = useMutation({
    mutationFn: ({ s, same }: { s: Suggestion; same: boolean }) =>
      decideCandidate(s.researcher_id, s.openalex_id, same),
    onSuccess: done,
    onError: fail,
  });
  const busy = approve.isPending || reject.isPending || decide.isPending;

  return (
    <>
      <section className={styles.section}>
        <h3 className={styles.h3}>Record corrections</h3>
        <p className={styles.hint}>
          Researchers saying a paper is not theirs, or that another author
          record is also them. An approved decision is kept through every data
          refresh.
        </p>
        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
        {!pending || pending.length === 0 ? (
          <p className={styles.hint}>No corrections waiting for review.</p>
        ) : (
          <ul className={styles.uploads}>
            {pending.map((c) => (
              <li key={c.id} className={styles.pendingItem}>
                <div className={styles.pendingHead}>
                  <Link
                    to={`/researchers/${c.researcher_id}`}
                    className={styles.pendingTitle}
                  >
                    {c.profile_name}
                  </Link>
                  <span className={styles.pendingMeta}>
                    {c.kind === "not_author"
                      ? "says a paper is not theirs"
                      : "says a record is also them"}
                  </span>
                </div>
                <Evidence c={c} />
                <div className={styles.pendingActions}>
                  <button
                    className={styles.primary}
                    disabled={busy}
                    onClick={() => approve.mutate(c.id)}
                  >
                    Approve
                  </button>
                  {rejecting === c.id ? (
                    <div className={styles.rejectRow}>
                      <input
                        className={styles.input}
                        placeholder="Reason shown to the researcher"
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        disabled={busy}
                      />
                      <button
                        className={styles.secondary}
                        disabled={busy}
                        onClick={() => reject.mutate({ id: c.id, why: note })}
                      >
                        Confirm reject
                      </button>
                      <button
                        className={styles.secondary}
                        disabled={busy}
                        onClick={() => setRejecting(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      className={styles.secondary}
                      disabled={busy}
                      onClick={() => {
                        setRejecting(c.id);
                        setNote("");
                      }}
                    >
                      Reject
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.h3}>Possibly the same person</h3>
        <p className={styles.hint}>
          Author records whose name fits a directory profile but which the
          automatic rules could not settle. Strongest evidence first.
        </p>
        {!candidates || candidates.length === 0 ? (
          <p className={styles.hint}>Nothing left to settle.</p>
        ) : (
          <ul className={styles.uploads}>
            {candidates.map((s) => (
              <li
                key={`${s.researcher_id}-${s.openalex_id}`}
                className={styles.pendingItem}
              >
                <div className={styles.pendingHead}>
                  <span className={styles.pendingTitle}>
                    <Link
                      to={`/researchers/${s.researcher_id}`}
                      className={styles.link}
                    >
                      {s.profile_name}
                    </Link>{" "}
                    and {s.other_name}?
                  </span>
                  <span className={styles.pendingMeta}>
                    {s.paper_count} paper{s.paper_count === 1 ? "" : "s"} ·{" "}
                    {s.shared_coauthors} co-author
                    {s.shared_coauthors === 1 ? "" : "s"} in common
                  </span>
                </div>
                <p className={styles.hint}>
                  {s.shared_areas.length > 0 && (
                    <>Shared areas: {s.shared_areas.join(", ")}. </>
                  )}
                  Papers: {s.papers.map((p) => p.title).join(" · ")}
                </p>
                <div className={styles.pendingActions}>
                  <button
                    className={styles.primary}
                    disabled={busy}
                    onClick={() => decide.mutate({ s, same: true })}
                  >
                    Same person
                  </button>
                  <button
                    className={styles.secondary}
                    disabled={busy}
                    onClick={() => decide.mutate({ s, same: false })}
                  >
                    Different people
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
