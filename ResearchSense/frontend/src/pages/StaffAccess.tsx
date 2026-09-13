import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { adminLogin, clearToken, fetchMe, getToken, setToken } from "../api/auth";
import { PageHeader } from "../components/PageHeader";
import { Loader } from "../components/StateViews";
import { AdminPanel } from "../features/portal/AdminPanel";
import styles from "../features/portal/portal.module.css";

/** Administrator sign-in, on its own quiet route.
 *
 * It used to be a fourth tab on /portal, which advertised the admin surface to
 * every visitor and invited password guessing from the front door. Nothing here
 * is secret — the protection is the password and the lockout — but there is no
 * reason to put the staff entrance on the public page, and no reason for a
 * researcher choosing how to sign in to be shown it at all.
 */
export default function StaffAccess() {
  const queryClient = useQueryClient();
  const [token, setSessionToken] = useState<string | null>(getToken());
  const [error, setError] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const { data: me, isLoading, refetch } = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    enabled: Boolean(token),
    retry: false,
  });

  const signOut = () => {
    clearToken();
    setSessionToken(null);
    queryClient.removeQueries({ queryKey: ["me"] });
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const res = await adminLogin(username, password);
      setToken(res.token);
      setSessionToken(res.token);
      void refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    }
  };

  const signedIn = Boolean(token) && !isLoading && me?.role === "admin";

  return (
    <>
      <PageHeader
        eyebrow="Staff access"
        title="Administration"
        description="Review submitted papers, manage claimed accounts, and run a data refresh."
      />
      <div className={`container ${styles.body}`}>
        {Boolean(token) && isLoading && <Loader />}

        {signedIn && <AdminPanel onSignOut={signOut} />}

        {!signedIn && !isLoading && (
          <div className={styles.authCard}>
            {error && (
              <p className={styles.error} role="alert">
                {error}
              </p>
            )}
            <form className={styles.form} onSubmit={submit}>
              <label className={styles.label}>
                Username
                <input
                  className={styles.input}
                  value={username}
                  required
                  onChange={(e) => setUsername(e.target.value.trim())}
                />
              </label>
              <label className={styles.label}>
                Password
                <input
                  className={styles.input}
                  type="password"
                  value={password}
                  required
                  onChange={(e) => setPassword(e.target.value)}
                />
              </label>
              <button type="submit" className={styles.primary}>
                Sign in
              </button>
            </form>
          </div>
        )}
      </div>
    </>
  );
}
