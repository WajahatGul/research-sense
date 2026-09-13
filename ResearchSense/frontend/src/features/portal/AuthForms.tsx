import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import {
  adminLogin,
  claimProfile,
  fetchClaimedIds,
  login,
  setToken,
} from "../../api/auth";
import { fetchResearchers } from "../../api/researchers";
import { INSTITUTION_NAME } from "../../config";
import { WorkspaceAuth } from "./WorkspaceAuth";
import styles from "./portal.module.css";

type Tab = "login" | "claim" | "institution" | "admin";

const TAB_LABEL: Record<Tab, string> = {
  login: "Faculty login",
  claim: "Claim profile",
  institution: "New institution",
  admin: "Admin",
};

export function AuthForms({ onSignedIn }: { onSignedIn: () => void }) {
  const [tab, setTab] = useState<Tab>("login");
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

  return (
    <>
    <div className={styles.guestCard}>
      <p className={styles.guestTitle}>Just looking around?</p>
      <p className={styles.guestText}>
        You do not need an account. Everyone can read the whole portal — the
        researchers, their publications, the analytics, and the assistant — and
        what you see is {INSTITUTION_NAME || "the deploying university"}'s real
        research data. Sign in below only to manage your own profile, or to set
        up a workspace for a different university.
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
      <div className={styles.tabs}>
        {(["login", "claim", "institution", "admin"] as Tab[]).map((t) => (
          <button key={t} onClick={() => { setTab(t); setError(""); }}
                  className={tab === t ? styles.tabActive : styles.tab}>
            {TAB_LABEL[t]}
          </button>
        ))}
      </div>

      {/* Above the form, not below it: the claim form is tall enough that an
          error under the submit button lands off-screen, so the user presses
          "Claim profile" and sees nothing happen. */}
      {error && <p className={styles.error} role="alert">{error}</p>}

      {tab === "login" && <LoginForm onSubmit={submit} />}
      {tab === "claim" && <ClaimForm onSubmit={submit} />}
      {tab === "institution" && <WorkspaceAuth onSignedIn={onSignedIn} />}
      {tab === "admin" && <AdminForm onSubmit={submit} />}
    </div>
    </>
  );
}

type Submit = (action: () => Promise<{ token: string }>) => void;

function LoginForm({ onSubmit }: { onSubmit: Submit }) {
  const [orcid, setOrcid] = useState("");
  const [password, setPassword] = useState("");
  return (
    <form className={styles.form}
          onSubmit={(e) => { e.preventDefault(); onSubmit(() => login(orcid, password)); }}>
      <label className={styles.label}>ORCID iD
        <input className={styles.input} value={orcid} required
               placeholder="0000-0000-0000-0000"
               onChange={(e) => setOrcid(e.target.value.trim())} />
      </label>
      <label className={styles.label}>Password
        <input className={styles.input} type="password" value={password} required
               onChange={(e) => setPassword(e.target.value)} />
      </label>
      <button type="submit" className={styles.primary}>Sign in</button>
    </form>
  );
}

function ClaimForm({ onSubmit }: { onSubmit: Submit }) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [orcid, setOrcid] = useState("");
  const [password, setPassword] = useState("");

  const { data: claimed } = useQuery({
    queryKey: ["claimed-ids"], queryFn: fetchClaimedIds,
  });
  const { data: matches } = useQuery({
    queryKey: ["claim-search", search],
    queryFn: () => fetchResearchers({ q: search, page_size: 8 }),
    enabled: search.length >= 3,
  });

  return (
    <form className={styles.form}
          onSubmit={(e) => {
            e.preventDefault();
            if (selected != null) onSubmit(() => claimProfile(selected, orcid, password));
          }}>
      <label className={styles.label}>Find your profile
        <input className={styles.input} value={search} placeholder="Type your name…"
               onChange={(e) => { setSearch(e.target.value); setSelected(null); }} />
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
                  <button type="button" disabled={taken}
                          className={styles.match}
                          onClick={() => { setSelected(r.researcher_id); setSearch(r.full_name); }}>
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
      <label className={styles.label}>Your ORCID iD
        <input className={styles.input} value={orcid} required
               placeholder="0000-0000-0000-0000"
               onChange={(e) => setOrcid(e.target.value.trim())} />
      </label>
      <p className={styles.hint}>
        It must be your own iD: the name on the public ORCID record is
        verified against the profile you are claiming.
      </p>
      <label className={styles.label}>Choose a password (8+ characters)
        <input className={styles.input} type="password" value={password}
               required minLength={8}
               onChange={(e) => setPassword(e.target.value)} />
      </label>
      <button type="submit" className={styles.primary} disabled={selected == null}
              title={selected == null
                ? "First select your profile from the name search above"
                : undefined}>
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

function AdminForm({ onSubmit }: { onSubmit: Submit }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  return (
    <form className={styles.form}
          onSubmit={(e) => { e.preventDefault(); onSubmit(() => adminLogin(username, password)); }}>
      <label className={styles.label}>Username
        <input className={styles.input} value={username} required
               onChange={(e) => setUsername(e.target.value)} />
      </label>
      <label className={styles.label}>Password
        <input className={styles.input} type="password" value={password} required
               onChange={(e) => setPassword(e.target.value)} />
      </label>
      <button type="submit" className={styles.primary}>Admin sign in</button>
    </form>
  );
}
