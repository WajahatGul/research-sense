import { useState } from "react";
import { Link } from "react-router-dom";

import { studyDoi, studyUpload } from "../../api/auth";
import styles from "./portal.module.css";

/** Library flow: index ANY paper for the assistant to answer questions
 *  about — no authorship requirement, no profile attribution. By DOI (the
 *  open-access PDF is fetched automatically) or by uploading the PDF. */
export function StudyPaper() {
  const [mode, setMode] = useState<"doi" | "upload">("doi");
  const [doi, setDoi] = useState("");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const run = async (work: () => Promise<string>) => {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      setStatus(await work());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  const sendDoi = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      const res = await studyDoi(doi);
      setDoi("");
      return `"${res.title}" — ${res.message}`;
    });
  };

  const sendUpload = (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    void run(async () => {
      const res = await studyUpload(title, file);
      setTitle("");
      setFile(null);
      return `"${res.title}" — ${res.message}`;
    });
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.h3}>Study a paper</h3>
      <p className={styles.hint}>
        Add any paper — yours or not — to the library, then ask about it on the{" "}
        <Link to="/ask" className={styles.link}>Ask ResearchSense</Link> page.
        It is not attributed to your profile.{" "}
        <button
          type="button"
          className={styles.link}
          style={{ background: "none", border: 0, cursor: "pointer", padding: 0 }}
          onClick={() => {
            setMode(mode === "doi" ? "upload" : "doi");
            setError("");
            setStatus("");
          }}
        >
          {mode === "doi" ? "Upload a PDF instead" : "Use a DOI instead"}
        </button>
      </p>

      {mode === "doi" ? (
        <form className={styles.form} onSubmit={sendDoi}>
          <label className={styles.label}>DOI
            <input className={styles.input} value={doi} required
                   placeholder="e.g. 10.1038/s41586-021-03819-2"
                   onChange={(e) => setDoi(e.target.value)} />
          </label>
          <button type="submit" className={styles.primary} disabled={busy}>
            {busy ? "Fetching and indexing…" : "Fetch and add to library"}
          </button>
        </form>
      ) : (
        <form className={styles.form} onSubmit={sendUpload}>
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
            {busy ? "Indexing…" : "Add to library"}
          </button>
        </form>
      )}

      {status && (
        <p className={styles.status}>
          {status}{" "}
          <Link to="/ask" className={styles.link}>
            Open the assistant →
          </Link>
        </p>
      )}
      {error && (
        <p className={styles.error}>
          {error}
          {error.toLowerCase().includes("already in the library") && (
            <>
              {" "}
              <Link to="/ask" className={styles.link}>
                Ask the assistant about it →
              </Link>
            </>
          )}
        </p>
      )}
    </section>
  );
}
