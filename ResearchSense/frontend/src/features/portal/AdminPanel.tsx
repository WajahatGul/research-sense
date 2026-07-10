import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  fetchAdminAccounts,
  fetchRefreshStatus,
  setAccountActive,
  triggerRefresh,
} from "../../api/auth";
import styles from "./portal.module.css";

export function AdminPanel({ onSignOut }: { onSignOut: () => void }) {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");

  const { data: accounts } = useQuery({
    queryKey: ["admin-accounts"], queryFn: fetchAdminAccounts,
  });
  const { data: refresh } = useQuery({
    queryKey: ["admin-refresh"], queryFn: fetchRefreshStatus,
    refetchInterval: 30_000,
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
