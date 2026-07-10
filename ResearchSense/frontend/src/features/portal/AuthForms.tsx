import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  adminLogin,
  claimProfile,
  fetchClaimedIds,
  login,
  setToken,
} from "../../api/auth";
import { fetchResearchers } from "../../api/researchers";
import styles from "./portal.module.css";

type Tab = "login" | "claim" | "admin";

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
    <div className={styles.authCard}>
      <div className={styles.tabs}>
        {(["login", "claim", "admin"] as Tab[]).map((t) => (
          <button key={t} onClick={() => { setTab(t); setError(""); }}
                  className={tab === t ? styles.tabActive : styles.tab}>
            {t === "login" ? "Faculty login" : t === "claim" ? "Claim profile" : "Admin"}
          </button>
        ))}
      </div>

      {tab === "login" && <LoginForm onSubmit={submit} />}
      {tab === "claim" && <ClaimForm onSubmit={submit} />}
      {tab === "admin" && <AdminForm onSubmit={submit} />}

      {error && <p className={styles.error}>{error}</p>}
    </div>
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
      )}
      <label className={styles.label}>Your ORCID iD
        <input className={styles.input} value={orcid} required
               placeholder="0000-0000-0000-0000"
               pattern="\d{4}-\d{4}-\d{4}-\d{3}[\dX]"
               onChange={(e) => setOrcid(e.target.value.trim())} />
      </label>
      <label className={styles.label}>Choose a password (8+ characters)
        <input className={styles.input} type="password" value={password}
               required minLength={8}
               onChange={(e) => setPassword(e.target.value)} />
      </label>
      <button type="submit" className={styles.primary} disabled={selected == null}>
        Claim profile
      </button>
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
