import { useState } from "react";

import {
  addWorkspaceDoi,
  applyCv,
  clearWorkspaceSession,
  parseCv,
  type CvDraft,
  type CvPublication,
  type WorkspaceSession,
} from "../../api/workspace";
import styles from "./portal.module.css";

interface Props {
  session: WorkspaceSession;
  onSignOut: () => void;
  onChanged: () => void;
}

const EMPTY_PUB: CvPublication = {
  title: "",
  publication_year: null,
  journal_name: "",
  doi: null,
};

export function WorkspaceDashboard({ session, onSignOut, onChanged }: Props) {
  const [cv, setCv] = useState("");
  const [draft, setDraft] = useState<CvDraft | null>(null);
  const [busy, setBusy] = useState<"" | "parsing" | "saving" | "doi">("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [doi, setDoi] = useState("");

  const readCv = async () => {
    setError("");
    setNotice("");
    setBusy("parsing");
    try {
      setDraft(await parseCv(cv));
      setNotice(
        "Here is what we read from your CV. Check and correct anything before saving — nothing is stored yet.",
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not read the CV");
    } finally {
      setBusy("");
    }
  };

  const save = async () => {
    if (!draft) return;
    setError("");
    setBusy("saving");
    try {
      const result = await applyCv(draft);
      setNotice(result.message);
      setDraft(null);
      setCv("");
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save");
    } finally {
      setBusy("");
    }
  };

  const addDoi = async () => {
    setError("");
    setNotice("");
    setBusy("doi");
    try {
      const result = await addWorkspaceDoi(doi);
      setNotice(result.message);
      setDoi("");
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add that DOI");
    } finally {
      setBusy("");
    }
  };

  const setField = (key: keyof CvDraft, value: string) =>
    setDraft((d) => (d ? { ...d, [key]: value } : d));

  const setPub = (i: number, patch: Partial<CvPublication>) =>
    setDraft((d) =>
      d
        ? {
            ...d,
            publications: d.publications.map((p, j) =>
              j === i ? { ...p, ...patch } : p,
            ),
          }
        : d,
    );

  const removePub = (i: number) =>
    setDraft((d) =>
      d ? { ...d, publications: d.publications.filter((_, j) => j !== i) } : d,
    );

  const addPub = () =>
    setDraft((d) =>
      d ? { ...d, publications: [...d.publications, { ...EMPTY_PUB }] } : d,
    );

  return (
    <div className={styles.dashboard}>
      <div className={styles.dashHead}>
        <div>
          <h2 className={styles.dashTitle}>{session.institution_name}</h2>
          <p className={styles.hint}>
            Signed in as {session.full_name}. This workspace holds only your
            institution's data.
          </p>
        </div>
        <button
          type="button"
          className={styles.secondary}
          onClick={() => {
            clearWorkspaceSession();
            onSignOut();
          }}
        >
          Sign out
        </button>
      </div>

      {notice && <p className={styles.status}>{notice}</p>}
      {error && <p className={styles.error}>{error}</p>}

      {!draft && (
        <>
          <h3 className={styles.sectionTitle}>Build your profile from your CV</h3>
          <p className={styles.hint}>
            Paste your CV below. We will read out your details and publications
            and show them in a form you can edit before anything is saved.
          </p>
          <textarea
            className={styles.textarea}
            rows={10}
            value={cv}
            placeholder="Paste the full text of your CV here…"
            onChange={(e) => setCv(e.target.value)}
          />
          <button
            type="button"
            className={styles.primary}
            disabled={cv.trim().length < 20 || busy !== ""}
            onClick={() => void readCv()}
          >
            {busy === "parsing" ? "Reading your CV…" : "Read my CV"}
          </button>

          <h3 className={styles.sectionTitle}>Or add a paper by DOI</h3>
          <div className={styles.doiRow}>
            <input
              className={styles.input}
              value={doi}
              placeholder="10.1109/ACCESS.2020.1234567"
              onChange={(e) => setDoi(e.target.value)}
            />
            <button
              type="button"
              className={styles.secondary}
              disabled={doi.trim().length < 6 || busy !== ""}
              onClick={() => void addDoi()}
            >
              {busy === "doi" ? "Adding…" : "Add paper"}
            </button>
          </div>
        </>
      )}

      {draft && (
        <>
          <h3 className={styles.sectionTitle}>Review and edit before saving</h3>

          <label className={styles.label}>Full name
            <input className={styles.input} value={draft.full_name}
                   onChange={(e) => setField("full_name", e.target.value)} />
          </label>
          <label className={styles.label}>Designation
            <input className={styles.input} value={draft.designation}
                   onChange={(e) => setField("designation", e.target.value)} />
          </label>
          <label className={styles.label}>Department
            <input className={styles.input} value={draft.department}
                   onChange={(e) => setField("department", e.target.value)} />
          </label>
          <label className={styles.label}>Education
            <input className={styles.input} value={draft.education}
                   onChange={(e) => setField("education", e.target.value)} />
          </label>
          <label className={styles.label}>Research areas (comma separated)
            <input
              className={styles.input}
              value={draft.research_areas.join(", ")}
              onChange={(e) =>
                setDraft((d) =>
                  d
                    ? {
                        ...d,
                        research_areas: e.target.value
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean),
                      }
                    : d,
                )
              }
            />
          </label>
          <label className={styles.label}>Short bio
            <textarea className={styles.textarea} rows={3} value={draft.profile_bio}
                      onChange={(e) => setField("profile_bio", e.target.value)} />
          </label>

          <h3 className={styles.sectionTitle}>
            Publications found ({draft.publications.length})
          </h3>
          {draft.publications.length === 0 && (
            <p className={styles.hint}>
              None were found in the CV. You can add them by hand below.
            </p>
          )}
          <ul className={styles.pubList}>
            {draft.publications.map((p, i) => (
              <li key={i} className={styles.pubEdit}>
                <input
                  className={styles.input}
                  value={p.title}
                  placeholder="Title"
                  onChange={(e) => setPub(i, { title: e.target.value })}
                />
                <div className={styles.pubMetaRow}>
                  <input
                    className={styles.input}
                    value={p.publication_year ?? ""}
                    placeholder="Year"
                    inputMode="numeric"
                    onChange={(e) =>
                      setPub(i, {
                        publication_year: e.target.value
                          ? Number(e.target.value.replace(/\D/g, "")) || null
                          : null,
                      })
                    }
                  />
                  <input
                    className={styles.input}
                    value={p.journal_name}
                    placeholder="Journal or venue"
                    onChange={(e) => setPub(i, { journal_name: e.target.value })}
                  />
                  <input
                    className={styles.input}
                    value={p.doi ?? ""}
                    placeholder="DOI (optional)"
                    onChange={(e) => setPub(i, { doi: e.target.value || null })}
                  />
                  <button
                    type="button"
                    className={styles.removeBtn}
                    aria-label="Remove this publication"
                    onClick={() => removePub(i)}
                  >
                    Remove
                  </button>
                </div>
              </li>
            ))}
          </ul>
          <button type="button" className={styles.secondary} onClick={addPub}>
            Add a publication
          </button>

          <div className={styles.doiRow}>
            <button
              type="button"
              className={styles.primary}
              disabled={busy !== ""}
              onClick={() => void save()}
            >
              {busy === "saving" ? "Saving…" : "Save to my profile"}
            </button>
            <button
              type="button"
              className={styles.secondary}
              disabled={busy !== ""}
              onClick={() => { setDraft(null); setNotice(""); }}
            >
              Discard
            </button>
          </div>
        </>
      )}
    </div>
  );
}
