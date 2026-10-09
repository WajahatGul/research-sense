import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getToken } from "../../api/auth";
import styles from "./portal.module.css";

interface Backup {
  name: string;
  at: string;
  size: number;
  counts: Record<string, number> | null;
}

async function call<T>(method: string, path: string): Promise<T> {
  const res = await fetch(path, { method, headers: { Authorization: `Bearer ${getToken()}` } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data as T;
}

const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

function contents(counts: Backup["counts"]): string {
  if (!counts) return "damaged, cannot be restored";
  const n = (k: string, one: string, many: string) =>
    `${counts[k] ?? 0} ${(counts[k] ?? 0) === 1 ? one : many}`;
  return [
    n("accounts", "account", "accounts"),
    n("claims", "claim", "claims"),
    n("corrections", "correction", "corrections"),
    n("submissions", "paper sent in", "papers sent in"),
    n("audit_log", "logged action", "logged actions"),
  ].join(" · ");
}

/** Copies of the accounts database, and putting one back.
 *
 * Claims, corrections, uploaded papers and the activity log exist nowhere
 * else, so they are copied daily. A restore is checked before it runs and
 * keeps a copy of what it replaces, so it can be undone.
 */
export function Backups() {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const { data } = useQuery({
    queryKey: ["admin-backups"],
    queryFn: () => call<{ backups: Backup[] }>("GET", "/api/admin/backups"),
  });
  const done = (text: string) => {
    setError("");
    setMessage(text);
    void queryClient.invalidateQueries();
  };
  const take = useMutation({
    mutationFn: () => call<Backup>("POST", "/api/admin/backups"),
    onSuccess: (b) => done(`Backup made: ${when(b.at)}.`),
    onError: (e: Error) => setError(e.message),
  });
  const restore = useMutation({
    mutationFn: (name: string) =>
      call<{ previous: string }>("POST", `/api/admin/backups/${encodeURIComponent(name)}/restore`),
    onSuccess: () =>
      done("Restored. The data it replaced was kept as a backup (marked \"before restore\"), so this can be undone."),
    onError: (e: Error) => setError(e.message),
  });

  const backups = data?.backups ?? [];
  const confirmRestore = (b: Backup) => {
    if (
      window.confirm(
        `Put back the accounts data from ${when(b.at)}?\n\n` +
          "Anything since then (claims, corrections, papers, log entries) is replaced. " +
          "The current data is backed up first, so you can undo this.",
      )
    ) {
      restore.mutate(b.name);
    }
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.h3}>Backups</h3>
      <p className={styles.hint}>
        Accounts, claims, corrections, papers sent in and the activity log are copied
        every day; the newest 14 copies are kept.
        {backups[0] ? ` Latest: ${when(backups[0].at)}.` : " No backup yet."}
      </p>
      <button className={styles.primary} onClick={() => take.mutate()} disabled={take.isPending}>
        {take.isPending ? "Backing up…" : "Back up now"}
      </button>
      {message && <p className={styles.status} role="status">{message}</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {backups.length > 0 && (
        <ul className={styles.uploads}>
          {backups.map((b) => (
            <li key={b.name} className={styles.upload}>
              <span>
                {when(b.at)}
                {b.name.includes("before-restore") && " (before restore)"}
                <span className={styles.uploadDate}> · {contents(b.counts)}</span>
              </span>
              <button
                type="button"
                className={styles.secondary}
                disabled={!b.counts || restore.isPending}
                onClick={() => confirmRestore(b)}
              >
                Restore
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
