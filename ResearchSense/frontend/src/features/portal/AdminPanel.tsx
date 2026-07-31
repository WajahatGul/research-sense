import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import type { PendingPaper } from "../../api/auth";
import {
  approvePaper,
  fetchAdminAccounts,
  fetchPendingPapers,
  fetchRefreshStatus,
  rejectPaper,
  setAccountActive,
  triggerRefresh,
} from "../../api/auth";
import { Badge } from "../../components/Badge";
import styles from "./portal.module.css";

// Human-readable venue/DOI line for a pending item's stored payload — shape
// differs by kind (publication vs. PDF upload), see PendingPaper.record.
function pendingSubtitle(p: PendingPaper): string {
  if (p.kind === "publication") {
    const { journal_name, publication_year, doi } = p.record as {
      journal_name?: string; publication_year?: number | string; doi?: string;
    };
    const parts = [
      journal_name || null,
      publication_year != null ? String(publication_year) : null,
      doi ? `DOI ${doi}` : null,
    ].filter(Boolean);
    return parts.join(" · ");
  }
  const { filename } = p.record as { filename?: string };
  return filename ?? "";
}

export function AdminPanel({ onSignOut }: { onSignOut: () => void }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [rejectingId, setRejectingId] = useState<number | null>(null);
  const [note, setNote] = useState("");

  const { data: accounts } = useQuery({
    queryKey: ["admin-accounts"], queryFn: fetchAdminAccounts,
  });
  const { data: refresh } = useQuery({
    queryKey: ["admin-refresh"], queryFn: fetchRefreshStatus,
    refetchInterval: 30_000,
  });
  const { data: pending } = useQuery({
    queryKey: ["admin-pending"], queryFn: fetchPendingPapers,
  });

  const toggle = async (orcid: string, active: boolean) => {
    await setAccountActive(orcid, active);
    queryClient.invalidateQueries({ queryKey: ["admin-accounts"] });
  };

  const startRefresh = async () => {
    setMessage("Refresh started. It re-fetches publications and rebuilds the index; this takes several minutes.");
    await triggerRefresh();
    queryClient.invalidateQueries({ queryKey: ["admin-refresh"] });
  };

  const approve = async (id: number) => {
    await approvePaper(id);
    queryClient.invalidateQueries({ queryKey: ["admin-pending"] });
  };

  const startReject = (id: number) => {
    setRejectingId(id);
    setNote("");
  };

  const cancelReject = () => {
    setRejectingId(null);
    setNote("");
  };

  const confirmReject = async (id: number) => {
    await rejectPaper(id, note);
    setRejectingId(null);
    setNote("");
    queryClient.invalidateQueries({ queryKey: ["admin-pending"] });
  };

  return (
    <div className={styles.dashboard}>
      <div className={styles.dashHead}>
        <h2 className={styles.dashTitle}>Administration</h2>
        <button className={styles.secondary} onClick={onSignOut}>Sign out</button>
      </div>

      <section className={styles.section}>
        <h3 className={styles.h3}>Data refresh</h3>
        <p className={styles.hint}>
          Last successful refresh:{" "}
          <span className="mono">
            {refresh?.last_refresh?.finished_at ?? "never (seed data in use)"}
          </span>
          {refresh?.due && " — a refresh is due."}
          {" "}The system also refreshes itself automatically every 7 days.
        </p>
        <button className={styles.primary} onClick={startRefresh}>
          Refresh data now
        </button>
        {message && <p className={styles.status}>{message}</p>}
      </section>

      <section className={styles.section}>
        <h3 className={styles.h3}>Pending papers</h3>
        {!pending || pending.length === 0 ? (
          <p className={styles.hint}>No papers waiting for review.</p>
        ) : (
          <ul className={styles.uploads}>
            {pending.map((p) => {
              const subtitle = pendingSubtitle(p);
              return (
                <li key={`${p.kind}-${p.id}`} className={styles.pendingItem}>
                  <div className={styles.pendingHead}>
                    <Badge tone={p.kind === "publication" ? "navy" : "default"}>
                      {p.kind === "publication" ? "Publication" : "PDF upload"}
                    </Badge>
                    <span className={styles.pendingTitle}>{p.title}</span>
                  </div>
                  <span className={styles.pendingMeta}>
                    Submitted by researcher #{p.researcher_id} ·{" "}
                    {p.submitted_at.slice(0, 10)}
                    {subtitle && ` · ${subtitle}`}
                  </span>
                  <div className={styles.pendingActions}>
                    <button className={styles.primary} onClick={() => approve(p.id)}>
                      Approve
                    </button>
                    {rejectingId === p.id ? (
                      <div className={styles.rejectRow}>
                        <input
                          className={styles.input}
                          placeholder="Optional note for the researcher"
                          value={note}
                          onChange={(e) => setNote(e.target.value)}
                        />
                        <button className={styles.secondary} onClick={() => confirmReject(p.id)}>
                          Confirm reject
                        </button>
                        <button className={styles.secondary} onClick={cancelReject}>
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button className={styles.secondary} onClick={() => startReject(p.id)}>
                        Reject
                      </button>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.h3}>Claimed profiles</h3>
        {!accounts || accounts.length === 0 ? (
          <p className={styles.hint}>No profiles have been claimed yet.</p>
        ) : (
          <ul className={styles.uploads}>
            {accounts.map((a) => (
              <li key={a.orcid_id} className={styles.upload}>
                <span>
                  {a.full_name}{" "}
                  <span className={`mono ${styles.uploadDate}`}>{a.orcid_id}</span>
                  {!a.active && <em> (deactivated)</em>}
                </span>
                <button className={styles.secondary}
                        onClick={() => toggle(a.orcid_id, !a.active)}>
                  {a.active ? "Deactivate" : "Reactivate"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
