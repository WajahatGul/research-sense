import { useState } from "react";
import { Link } from "react-router-dom";

import type { Me } from "../../api/auth";
import { uploadPaper } from "../../api/auth";
import styles from "./portal.module.css";

export function FacultyDashboard({ me, onChanged, onSignOut }: {
  me: Me;
  onChanged: () => void;
  onSignOut: () => void;
}) {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || busy) return;
    setBusy(true);
    setStatus("Uploading and indexing…");
    try {
      const res = await uploadPaper(title, file);
      setStatus(res.message);
      setTitle("");
      setFile(null);
      onChanged();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.dashboard}>
      <div className={styles.dashHead}>
        <div>
          <h2 className={styles.dashTitle}>Welcome, {me.full_name}</h2>
          <p className={styles.dashSub}>
            ORCID <span className="mono">{me.orcid_id}</span> ·{" "}
            <Link to={`/researchers/${me.researcher_id}`} className={styles.link}>
              View public profile
            </Link>
          </p>
        </div>
        <button className={styles.secondary} onClick={onSignOut}>Sign out</button>
      </div>

      <section className={styles.section}>
        <h3 className={styles.h3}>Upload a paper</h3>
        <p className={styles.hint}>
          PDF up to 15 MB. It is added to the assistant's knowledge immediately,
          so anyone can ask questions about it.
        </p>
        <form className={styles.form} onSubmit={submit}>
          <label className={styles.label}>Paper title
            <input className={styles.input} value={title} required minLength={5}
                   placeholder="Exact title of the paper"
                   onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className={styles.label}>PDF file
            <input className={styles.input} type="file" accept="application/pdf"
                   required onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </label>
          <button type="submit" className={styles.primary} disabled={busy}>
            {busy ? "Indexing…" : "Upload and index"}
          </button>
        </form>
        {status && <p className={styles.status}>{status}</p>}
      </section>

      <section className={styles.section}>
        <h3 className={styles.h3}>Your uploaded papers</h3>
        {me.uploads.length === 0 ? (
          <p className={styles.hint}>Nothing uploaded yet.</p>
        ) : (
          <ul className={styles.uploads}>
            {me.uploads.map((u) => (
              <li key={u.filename} className={styles.upload}>
                <span>{u.title}</span>
                <span className={`mono ${styles.uploadDate}`}>
                  {u.uploaded_at.slice(0, 10)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
