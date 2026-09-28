import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchMe, getToken } from "../../api/auth";
import styles from "./portal.module.css";

interface AdminRow {
  username: string;
  active: number;
  weak_password: number;
  created_at: string;
  created_by: string | null;
}

interface Activity {
  id: number;
  at: string;
  actor: string;
  action: string;
  target: string | null;
  detail: string | null;
}

async function call<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data as T;
}

// Plain words for what each logged action means.
const ACTION: Record<string, string> = {
  "admin.login": "signed in",
  "admin.login_failed": "failed to sign in",
  "admin.created": "added administrator",
  "admin.activated": "reactivated administrator",
  "admin.deactivated": "deactivated administrator",
  "admin.password_changed": "changed their password",
  "claim.approved": "approved a profile claim",
  "claim.rejected": "rejected a profile claim",
  "account.activated": "reactivated account",
  "account.deactivated": "deactivated account",
  "paper.approved": "approved a paper",
  "paper.rejected": "rejected a paper",
  "correction.approved": "approved a record correction",
  "correction.rejected": "rejected a record correction",
  "identity.same_person": "merged an author record into",
  "identity.different_people": "marked as a different person from",
  "refresh.started": "started a data refresh",
  "backup.taken": "made a backup",
  "backup.restored": "restored the backup",
};

/** Who can administer, and what each of them has done.
 *
 * One shared login used to make every decision anonymous. Each administrator
 * now has their own account, and every approval, rejection and change of
 * access is written to a log that can be read but never edited.
 */
export function AdminSecurity() {
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const { data: me } = useQuery({ queryKey: ["me"], queryFn: fetchMe });
  const { data: admins } = useQuery({
    queryKey: ["admin-admins"],
    queryFn: () => call<AdminRow[]>("GET", "/api/admin/admins"),
  });
  const { data: activity } = useQuery({
    queryKey: ["admin-activity"],
    queryFn: () => call<Activity[]>("GET", "/api/admin/activity?limit=30"),
    refetchInterval: 30_000,
  });

  const refresh = () => {
    setError("");
    void queryClient.invalidateQueries({ queryKey: ["admin-admins"] });
    void queryClient.invalidateQueries({ queryKey: ["admin-activity"] });
    void queryClient.invalidateQueries({ queryKey: ["me"] });
  };
  const fail = (e: unknown) => {
    setMessage("");
    setError(e instanceof Error ? e.message : "Something went wrong");
  };
  const add = useMutation({
    mutationFn: () => call("POST", "/api/admin/admins", { username, password }),
    onSuccess: () => {
      setMessage(
        `Added ${username}. Give them their password in person, not by email.`,
      );
      setUsername("");
      setPassword("");
      refresh();
    },
    onError: fail,
  });
  const toggle = useMutation({
    mutationFn: (a: AdminRow) =>
      call(
        "POST",
        `/api/admin/admins/${encodeURIComponent(a.username)}/active?active=${!a.active}`,
      ),
    onSuccess: refresh,
    onError: fail,
  });
  const change = useMutation({
    mutationFn: () =>
      call("POST", "/api/admin/password", { current, new: next }),
    onSuccess: () => {
      setMessage("Password changed.");
      setCurrent("");
      setNext("");
      refresh();
    },
    onError: fail,
  });

  return (
    <>
      {me?.password_weak && (
        <section
          className={`${styles.section} ${styles.warnCard}`}
          role="alert"
        >
          <h3 className={styles.h3}>Change your password</h3>
          <p className={styles.hint}>
            This account still uses the short password from the server settings.
            Anyone who guesses it can approve claims and change records. Choose
            one of at least 12 characters.
          </p>
          <form
            className={styles.form}
            onSubmit={(e) => {
              e.preventDefault();
              change.mutate();
            }}
          >
            <label className={styles.label}>
              Current password
              <input
                className={styles.input}
                type="password"
                value={current}
                required
                onChange={(e) => setCurrent(e.target.value)}
              />
            </label>
            <label className={styles.label}>
              New password (12+ characters)
              <input
                className={styles.input}
                type="password"
                value={next}
                required
                minLength={12}
                onChange={(e) => setNext(e.target.value)}
              />
            </label>
            <button className={styles.primary} disabled={change.isPending}>
              Change password
            </button>
          </form>
        </section>
      )}

      {message && (
        <p className={styles.status} role="status">
          {message}
        </p>
      )}
      {error && (
        <p className={styles.error} role="alert">
          {error}
        </p>
      )}

      <section className={styles.section}>
        <h3 className={styles.h3}>Administrators</h3>
        <p className={styles.hint}>
          Everyone who administers the portal signs in as themselves, so every
          decision below has a name on it.
        </p>
        <ul className={styles.uploads}>
          {admins?.map((a) => (
            <li key={a.username} className={styles.upload}>
              <span>
                <strong>{a.username}</strong>
                {a.username === me?.full_name && " (you)"}
                {!a.active && <em> (deactivated)</em>}
                {a.weak_password ? <em> · weak password</em> : null}
                <span className={styles.uploadDate}>
                  {" "}
                  · added {a.created_at.slice(0, 10)}
                  {a.created_by ? ` by ${a.created_by}` : ""}
                </span>
              </span>
              {a.username !== me?.full_name && (
                <button
                  className={styles.secondary}
                  disabled={toggle.isPending}
                  onClick={() => toggle.mutate(a)}
                >
                  {a.active ? "Deactivate" : "Reactivate"}
                </button>
              )}
            </li>
          ))}
        </ul>
        <form
          className={styles.form}
          onSubmit={(e) => {
            e.preventDefault();
            add.mutate();
          }}
        >
          <label className={styles.label}>
            New administrator's username
            <input
              className={styles.input}
              value={username}
              required
              minLength={3}
              onChange={(e) => setUsername(e.target.value)}
            />
          </label>
          <label className={styles.label}>
            Their password (12+ characters)
            <input
              className={styles.input}
              type="password"
              value={password}
              required
              minLength={12}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button className={styles.primary} disabled={add.isPending}>
            Add administrator
          </button>
        </form>
      </section>

      <section className={styles.section}>
        <h3 className={styles.h3}>Activity</h3>
        <p className={styles.hint}>
          Every sign-in, approval, rejection and change of access, newest first.
          It can be read here but never edited.
        </p>
        {!activity || activity.length === 0 ? (
          <p className={styles.hint}>Nothing recorded yet.</p>
        ) : (
          <ul className={styles.activity}>
            {activity.map((e) => (
              <li
                key={e.id}
                className={
                  e.action === "admin.login_failed"
                    ? styles.activityWarn
                    : undefined
                }
              >
                <span className={`mono ${styles.uploadDate}`}>
                  {e.at.slice(0, 16).replace("T", " ")}
                </span>{" "}
                <strong>{e.actor}</strong> {ACTION[e.action] ?? e.action}
                {e.target ? ` ${e.target}` : ""}
                {e.detail ? (
                  <span className={styles.uploadDate}> · {e.detail}</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
