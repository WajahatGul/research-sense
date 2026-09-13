import { useState } from "react";

import {
  loginWorkspace,
  saveWorkspaceSession,
  signUpWorkspace,
  type WorkspaceSession,
} from "../../api/workspace";
import styles from "./portal.module.css";

/** Sign-up / sign-in for an institution that is not in the demo corpus.
 *  A new workspace starts empty: none of the demo data is visible in it. */
export function WorkspaceAuth({
  onSignedIn,
  mode: controlled,
}: {
  onSignedIn: () => void;
  /** Set by the portal, which owns the sign-in / create-account switch. Left
   *  undefined the component keeps its own toggle, for standalone use. */
  mode?: "signup" | "signin";
}) {
  const [ownMode, setOwnMode] = useState<"signup" | "signin">("signup");
  const mode = controlled ?? ownMode;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [institution, setInstitution] = useState("");
  const [fullName, setFullName] = useState("");
  const [department, setDepartment] = useState("");
  const [campus, setCampus] = useState("");

  const run = async (action: () => Promise<WorkspaceSession>) => {
    setError("");
    setBusy(true);
    try {
      saveWorkspaceSession(await action());
      onSignedIn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        if (mode === "signin") {
          void run(() => loginWorkspace(email, password));
        } else {
          void run(() =>
            signUpWorkspace({
              email,
              password,
              institution_name: institution,
              full_name: fullName,
              department,
              campus: campus || "Main campus",
            }),
          );
        }
      }}
    >
      <p className={styles.hint}>
        {mode === "signup"
          ? "Create a space for your own university. It starts empty — you add your own profile and papers, and none of the demo data appears in it."
          : "Sign in to your institution's workspace."}
      </p>

      {mode === "signup" && (
        <>
          <label className={styles.label}>Institution
            <input className={styles.input} value={institution} required
                   placeholder="e.g. Meridian University"
                   onChange={(e) => setInstitution(e.target.value)} />
          </label>
          <label className={styles.label}>Your full name
            <input className={styles.input} value={fullName} required
                   placeholder="e.g. Dr Sara Ahmed"
                   onChange={(e) => setFullName(e.target.value)} />
          </label>
          <label className={styles.label}>Department
            <input className={styles.input} value={department}
                   placeholder="e.g. Computer Science"
                   onChange={(e) => setDepartment(e.target.value)} />
          </label>
          <label className={styles.label}>Campus (optional)
            <input className={styles.input} value={campus}
                   placeholder="Main campus"
                   onChange={(e) => setCampus(e.target.value)} />
          </label>
        </>
      )}

      <label className={styles.label}>Email
        <input className={styles.input} type="email" value={email} required
               onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label className={styles.label}>
        Password{mode === "signup" ? " (8+ characters)" : ""}
        <input className={styles.input} type="password" value={password} required
               minLength={mode === "signup" ? 8 : undefined}
               onChange={(e) => setPassword(e.target.value)} />
      </label>

      <button type="submit" className={styles.primary} disabled={busy}>
        {busy
          ? "Please wait…"
          : mode === "signup"
            ? "Create my workspace"
            : "Sign in"}
      </button>

      {error && <p className={styles.error}>{error}</p>}

      {controlled === undefined && (
        <button
          type="button"
          className={styles.linkButton}
          onClick={() => {
            setOwnMode(mode === "signup" ? "signin" : "signup");
            setError("");
          }}
        >
          {mode === "signup"
            ? "Already have a workspace? Sign in"
            : "New institution? Create an account"}
        </button>
      )}
    </form>
  );
}
