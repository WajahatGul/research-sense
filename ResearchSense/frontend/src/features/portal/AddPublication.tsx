import { useState } from "react";

import type { DoiPreview } from "../../api/auth";
import { previewDoi, submitDoi, submitManualPublication } from "../../api/auth";
import styles from "./portal.module.css";

/** Publication submission per the proposal's ingestion pipeline:
 *  DOI-based (Crossref fetch -> verify -> confirm) with a manual-entry
 *  fallback for works that have no DOI. */
export function AddPublication({ onAdded }: { onAdded: () => void }) {
  const [mode, setMode] = useState<"doi" | "manual">("doi");

  // DOI flow
  const [doi, setDoi] = useState("");
  const [preview, setPreview] = useState<DoiPreview | null>(null);

  // Manual flow
  const [title, setTitle] = useState("");
  const [venue, setVenue] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [pubType, setPubType] = useState("journal");

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

  const fetchPreview = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      setPreview(await previewDoi(doi));
      return "";
    });
  };

  const confirmDoi = () =>
    void run(async () => {
      const res = await submitDoi(doi);
      setPreview(null);
      setDoi("");
      onAdded();
      return res.message;
    });

  const sendManual = (e: React.FormEvent) => {
    e.preventDefault();
    void run(async () => {
      const res = await submitManualPublication({
        title,
        journal_name: venue,
        publication_year: year,
        publication_type: pubType,
      });
      setTitle("");
      setVenue("");
      onAdded();
      return res.message;
    });
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.h3}>Add a publication</h3>
      <p className={styles.hint}>
        Enter a DOI and we fetch the details from Crossref for you to verify.
        No DOI?{" "}
        <button
          type="button"
          className={styles.link}
          style={{ background: "none", border: 0, cursor: "pointer", padding: 0 }}
          onClick={() => {
            setMode(mode === "doi" ? "manual" : "doi");
            setPreview(null);
            setError("");
            setStatus("");
          }}
        >
          {mode === "doi" ? "Enter the details manually" : "Use a DOI instead"}
        </button>
      </p>

      {mode === "doi" ? (
        <>
          <form className={styles.form} onSubmit={fetchPreview}>
            <label className={styles.label}>DOI
              <input className={styles.input} value={doi} required
                     placeholder="e.g. 10.1038/nature14539 or a doi.org link"
                     onChange={(e) => { setDoi(e.target.value); setPreview(null); }} />
            </label>
            <button type="submit" className={styles.primary} disabled={busy}>
              {busy && !preview ? "Fetching…" : "Fetch details"}
            </button>
          </form>

          {preview && (
            <div className={styles.preview}>
              <p className={styles.previewTitle}>{preview.title}</p>
              <p className={styles.previewMeta}>
                {preview.authors.join(", ") || "Authors unavailable"}
              </p>
              <p className={styles.previewMeta}>
                {preview.journal_name} · {preview.publication_year} ·{" "}
                {preview.publication_type} ·{" "}
                {preview.citation_count.toLocaleString()} citations
              </p>
              {preview.topics.length > 0 && (
                <p className={styles.previewMeta}>
                  Topics: {preview.topics.join(", ")}
                </p>
              )}
              {preview.concepts.length > 0 && (
                <p className={styles.previewMeta}>
                  Concept fingerprint: {preview.concepts.join(" · ")}
                </p>
              )}
              {preview.duplicate ? (
                <p className={styles.error}>
                  Already in the database{preview.duplicate_of
                    ? ` as "${preview.duplicate_of}"` : ""}.
                </p>
              ) : !preview.authorship_ok ? (
                <p className={styles.error}>
                  {preview.authorship_message ??
                    "You do not appear in this paper's author list."}
                </p>
              ) : (
                <button className={styles.primary} disabled={busy}
                        onClick={confirmDoi}>
                  {busy ? "Adding…" : "Confirm and add"}
                </button>
              )}
            </div>
          )}
        </>
      ) : (
        <form className={styles.form} onSubmit={sendManual}>
          <label className={styles.label}>Title
            <input className={styles.input} value={title} required minLength={5}
                   placeholder="Exact title of the publication"
                   onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label className={styles.label}>Venue (journal or conference)
            <input className={styles.input} value={venue}
                   placeholder="e.g. IEEE Access"
                   onChange={(e) => setVenue(e.target.value)} />
          </label>
          <div className={styles.rowPair}>
            <label className={styles.label}>Year
              <input className={styles.input} type="number" value={year}
                     min={1950} max={2100} required
                     onChange={(e) => setYear(Number(e.target.value))} />
            </label>
            <label className={styles.label}>Type
              <select className={styles.input} value={pubType}
                      onChange={(e) => setPubType(e.target.value)}>
                <option value="journal">Journal</option>
                <option value="conference">Conference</option>
              </select>
            </label>
          </div>
          <button type="submit" className={styles.primary} disabled={busy}>
            {busy ? "Adding…" : "Add publication"}
          </button>
        </form>
      )}

      {status && <p className={styles.status}>{status}</p>}
      {error && <p className={styles.error}>{error}</p>}
    </section>
  );
}
