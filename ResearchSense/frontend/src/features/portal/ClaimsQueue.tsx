import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { approveClaim, fetchPendingClaims, rejectClaim } from "../../api/auth";
import styles from "./portal.module.css";

/** Profile claims waiting for a decision.
 *
 * A claim made by typing an ORCID iD proves nothing on its own (iDs are
 * public), so it waits here with what the public ORCID record says: the names
 * on it and the organisations it lists as employers. Approving one claim
 * turns down any other claim on the same profile.
 */
export function ClaimsQueue() {
  const queryClient = useQueryClient();
  const [rejecting, setRejecting] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const { data: claims } = useQuery({
    queryKey: ["admin-claims"],
    queryFn: fetchPendingClaims,
  });
  const done = () => {
    setRejecting(null);
    setNote("");
    setError("");
    queryClient.invalidateQueries({ queryKey: ["admin-claims"] });
    queryClient.invalidateQueries({ queryKey: ["admin-accounts"] });
  };
  const fail = (err: unknown) =>
    setError(err instanceof Error ? err.message : "Could not update the claim.");
  const approve = useMutation({ mutationFn: approveClaim, onSuccess: done, onError: fail });
  const reject = useMutation({
    mutationFn: ({ id, why }: { id: number; why: string }) => rejectClaim(id, why),
    onSuccess: done,
    onError: fail,
  });
  const busy = approve.isPending || reject.isPending;

  return (
    <section className={styles.section}>
      <h3 className={styles.h3}>Profile claims</h3>
      <p className={styles.hint}>
        Typing an ORCID iD does not prove it is yours: iDs are public. Check the
        ORCID record against the profile before approving.
      </p>
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}
      {!claims || claims.length === 0 ? (
        <p className={styles.hint}>No claims waiting for review.</p>
      ) : (
        <ul className={styles.uploads}>
          {claims.map((c) => (
            <li key={c.id} className={styles.pendingItem}>
              <div className={styles.pendingHead}>
                <span className={styles.pendingTitle}>{c.profile_name}</span>
                {c.orcid_verified && (
                  <span className={`${styles.statusChip} ${styles.statusApproved}`}>
                    Signed in at ORCID
                  </span>
                )}
                {c.competing_claims > 0 && (
                  <strong className={styles.claimWarn}>
                    {c.competing_claims} other claim{c.competing_claims === 1 ? "" : "s"} on
                    this profile
                  </strong>
                )}
              </div>
              <dl className={styles.evidence}>
                <dt>Profile</dt>
                <dd>
                  {[c.profile_department, c.profile_campus].filter(Boolean).join(" · ") || "—"}
                </dd>
                <dt>ORCID record</dt>
                <dd>
                  <a
                    href={`https://orcid.org/${c.orcid_id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="mono"
                  >
                    {c.orcid_id} ↗
                  </a>
                  {c.orcid_names.length > 0 && ` · ${c.orcid_names.join(", ")}`}
                </dd>
                <dt>Employers listed</dt>
                <dd>
                  {c.orcid_employers.length > 0
                    ? c.orcid_employers.join(", ")
                    : "None public — ask the claimant for proof"}
                </dd>
                <dt>Submitted</dt>
                <dd>{c.submitted_at.slice(0, 10)}</dd>
              </dl>
              <div className={styles.pendingActions}>
                <button
                  className={styles.primary}
                  onClick={() => approve.mutate(c.id)}
                  disabled={busy}
                >
                  Approve
                </button>
                {rejecting === c.id ? (
                  <div className={styles.rejectRow}>
                    <input
                      className={styles.input}
                      placeholder="Reason shown to the claimant"
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      disabled={busy}
                    />
                    <button
                      className={styles.secondary}
                      onClick={() => reject.mutate({ id: c.id, why: note })}
                      disabled={busy}
                    >
                      Confirm reject
                    </button>
                    <button
                      className={styles.secondary}
                      onClick={() => setRejecting(null)}
                      disabled={busy}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    className={styles.secondary}
                    onClick={() => {
                      setRejecting(c.id);
                      setNote("");
                    }}
                    disabled={busy}
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
  );
}
