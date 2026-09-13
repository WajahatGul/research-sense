import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import {
  beginOrcidClaim,
  claimProfile,
  fetchClaimedIds,
  login,
  orcidSignInAvailable,
  setToken,
} from "../../api/auth";
import { fetchResearchers } from "../../api/researchers";
import { INSTITUTION_NAME } from "../../config";
import { WorkspaceAuth } from "./WorkspaceAuth";
import styles from "./portal.module.css";

/** The sign-in card.
 *
 * This began as four tabs — Faculty login, Claim profile, New institution,
 * Admin — three identity systems and a staff entrance side by side, with
 * nothing telling a visitor which was theirs. Asking "which are you?" up front
 * fixed the confusion but read like a wizard rather than a sign-in page.
 *
 * So it follows the shape people already know: sign in by default, "don't have
 * an account?" underneath, and the only real fork — a researcher here versus an
 * institution bringing its own data — as a small switch rather than a choice
 * the visitor has to make before seeing anything.
 */
type Mode = "signin" | "create";
type Kind = "researcher" | "institution";

export function AuthForms({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<Mode>("signin");
  const [kind, setKind] = useState<Kind>("researcher");
  const [error, setError] = useState("");

  const submit = async (action: () => Promise<{ token: string }>) => {
    setError("");
    try {
      const res = await action();
      setToken(res.token);
      onSignedIn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    }
  };

  const institution = INSTITUTION_NAME || "this university";
  const switchTo = (next: Kind) => {
    setKind(next);
    setError("");
  };

  return (
    <>
      <div className={styles.guestCard}>
        <p className={styles.guestTitle}>Just looking around?</p>
        <p className={styles.guestText}>
          You do not need an account. Everyone can read the whole portal — the
          researchers, their publications, the analytics, and the assistant —
          and what you see is {institution}'s real research data.
        </p>
        <div className={styles.guestLinks}>
          <Link className={styles.guestLink} to="/researchers">
            Browse researchers
          </Link>
          <Link className={styles.guestLink} to="/analytics">
            See the analytics
          </Link>
          <Link className={styles.guestLink} to="/ask">
            Ask the assistant
          </Link>
        </div>
      </div>

      <div className={styles.authCard}>
        <h2 className={styles.cardTitle}>
          {mode === "signin" ? "Sign in" : "Create your account"}
        </h2>

        <div className={styles.segmented} role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={kind === "researcher"}
            className={kind === "researcher" ? styles.segOn : styles.seg}
            onClick={() => switchTo("researcher")}
          >
            {institution}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={kind === "institution"}
            className={kind === "institution" ? styles.segOn : styles.seg}
            onClick={() => switchTo("institution")}
          >
            Another university
          </button>
        </div>

        {/* Above the form, not below it: the claim form is tall enough that an
            error under the submit button lands off-screen, so the user presses
            the button and sees nothing happen. */}
        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}

        {kind === "researcher" &&
          (mode === "signin" ? (
            <LoginForm onSubmit={submit} />
          ) : (
            <ClaimForm onSubmit={submit} onError={setError} />
          ))}

        {kind === "institution" && (
          <WorkspaceAuth
            onSignedIn={onSignedIn}
            mode={mode === "signin" ? "signin" : "signup"}
          />
        )}

        <p className={styles.footNote}>
          {mode === "signin" ? (
            <>
              {/* "Don't have an account? Create an account" repeats itself;
                  "New here?" carries the same meaning and works for both. */}
              New here?{" "}
              <button
                type="button"
                className={styles.linkInline}
                onClick={() => {
                  setMode("create");
                  setError("");
                }}
              >
                {kind === "researcher"
                  ? "Claim your profile"
                  : "Create an account"}
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                className={styles.linkInline}
                onClick={() => {
                  setMode("signin");
                  setError("");
                }}
              >
                Sign in
              </button>
            </>
          )}
        </p>
      </div>
    </>
  );
}

type Submit = (action: () => Promise<{ token: string }>) => void;

function LoginForm({ onSubmit }: { onSubmit: Submit }) {
  const [orcid, setOrcid] = useState("");
  const [password, setPassword] = useState("");
  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(() => login(orcid, password));
      }}
    >
      <label className={styles.label}>
        ORCID iD
        <input
          className={styles.input}
          value={orcid}
          required
          placeholder="0000-0000-0000-0000"
          onChange={(e) => setOrcid(e.target.value.trim())}
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
  );
}

function ClaimForm({
  onSubmit,
  onError,
}: {
  onSubmit: Submit;
  onError: (message: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [orcid, setOrcid] = useState("");
  const [password, setPassword] = useState("");
  const [sending, setSending] = useState(false);

  const { data: claimed } = useQuery({
    queryKey: ["claimed-ids"],
    queryFn: fetchClaimedIds,
  });
  const { data: matches } = useQuery({
    queryKey: ["claim-search", search],
    queryFn: () => fetchResearchers({ q: search, page_size: 8 }),
    enabled: search.length >= 3,
  });
  // When an ORCID client is configured the researcher proves the iD is theirs
  // by signing in at orcid.org. Otherwise we fall back to matching the name on
  // the public record, and say so rather than implying more.
  const { data: canVerify } = useQuery({
    queryKey: ["orcid-available"],
    queryFn: orcidSignInAvailable,
  });

  const startOrcid = async () => {
    if (selected == null) return;
    setSending(true);
    try {
      const { authorize_url } = await beginOrcidClaim(selected, password);
      window.location.href = authorize_url;
    } catch (e) {
      onError(e instanceof Error ? e.message : "Could not start ORCID sign-in");
      setSending(false);
    }
  };

  const picker = (
    <>
      <label className={styles.label}>
        Find your profile
        <input
          className={styles.input}
          value={search}
          placeholder="Type your name…"
          onChange={(e) => {
            setSearch(e.target.value);
            setSelected(null);
          }}
        />
      </label>
      {matches && selected == null && (
        <>
          <p className={styles.hint}>
            {matches.items.length === 0
              ? "No matching researcher found — try a different spelling."
              : "Click your name below to select your profile:"}
          </p>
          <ul className={styles.matches}>
            {matches.items.map((r) => {
              const taken = claimed?.includes(r.researcher_id);
              return (
                <li key={r.researcher_id}>
                  <button
                    type="button"
                    disabled={taken}
                    className={styles.match}
                    onClick={() => {
                      setSelected(r.researcher_id);
                      setSearch(r.full_name);
                    }}
                  >
                    {r.full_name} · {r.campus} {taken && "(already claimed)"}
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
      {selected != null && (
        <p className={styles.status}>Profile selected: {search} ✓</p>
      )}
      <label className={styles.label}>
        Choose a password (8+ characters)
        <input
          className={styles.input}
          type="password"
          value={password}
          required
          minLength={8}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
    </>
  );

  if (canVerify) {
    return (
      <form
        className={styles.form}
        onSubmit={(e) => {
          e.preventDefault();
          void startOrcid();
        }}
      >
        {picker}
        <p className={styles.hint}>
          You will sign in at orcid.org to prove the iD is yours. We never see
          your ORCID password.
        </p>
        <button
          type="submit"
          className={styles.primary}
          disabled={selected == null || password.length < 8 || sending}
        >
          {sending ? "Redirecting to ORCID…" : "Verify with ORCID"}
        </button>
        {selected == null && (
          <p className={styles.hint}>
            The button activates after you select your profile above.
          </p>
        )}
      </form>
    );
  }

  return (
    <form
      className={styles.form}
      onSubmit={(e) => {
        e.preventDefault();
        if (selected != null) onSubmit(() => claimProfile(selected, orcid, password));
      }}
    >
      {picker}
      <label className={styles.label}>
        Your ORCID iD
        <input
          className={styles.input}
          value={orcid}
          required
          placeholder="0000-0000-0000-0000"
          onChange={(e) => setOrcid(e.target.value.trim())}
        />
      </label>
      <p className={styles.hint}>
        It must be your own iD: the name on the public ORCID record is checked
        against the profile you are claiming.
      </p>
      <button
        type="submit"
        className={styles.primary}
        disabled={selected == null}
        title={
          selected == null
            ? "First select your profile from the name search above"
            : undefined
        }
      >
        Claim profile
      </button>
      {selected == null && (
        <p className={styles.hint}>
          The button activates after you select your profile from the search
          results above.
        </p>
      )}
    </form>
  );
}
