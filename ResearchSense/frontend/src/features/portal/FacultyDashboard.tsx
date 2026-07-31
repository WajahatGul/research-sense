import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { Me, MySubmission } from "../../api/auth";
import { fetchMySubmissions, uploadPaper } from "../../api/auth";
import { fetchPublications } from "../../api/publications";
import { AddPublication } from "./AddPublication";
import { StudyPaper } from "./StudyPaper";
import styles from "./portal.module.css";

function kindLabel(kind: string): string {
  if (kind === "publication") return "Publication";
  if (kind === "upload") return "PDF upload";
  return kind;
}

function statusClass(status: MySubmission["status"]): string {
  if (status === "approved") return styles.statusApproved;
  if (status === "rejected") return styles.statusRejected;
  return styles.statusPending;
}

export function FacultyDashboard({ me, onChanged, onSignOut }: {
  me: Me;
  onChanged: () => void;
  onSignOut: () => void;
}) {
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const queryClient = useQueryClient();
  // The researcher's publications (openalex + DOI/manual submissions), so a
  // submission is visible right here instead of only on the public pages.
  const { data: myPubs } = useQuery({
    queryKey: ["my-publications", me.researcher_id],
    queryFn: () => fetchPublications({
      author_id: me.researcher_id ?? undefined, page_size: 100 }),
    enabled: me.researcher_id != null,
  });
  // Submissions awaiting/reviewed by an admin — publications and uploads
  // don't show up elsewhere on the profile until approved, so this is the
  // only place a researcher can see them in the meantime.
  const { data: mySubmissions } = useQuery({
    queryKey: ["my-submissions", me.researcher_id],
    queryFn: fetchMySubmissions,
    enabled: me.researcher_id != null,
  });

  // A submission changes publications, profiles, analytics, and the chat
  // index — drop every cached query so all pages refetch fresh data.
  const afterSubmission = () => {
    void queryClient.invalidateQueries();
    onChanged();
  };

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
      afterSubmission();
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

      <AddPublication onAdded={afterSubmission} />

      <section className={styles.section}>
        <h3 className={styles.h3}>My submissions</h3>
        <p className={styles.hint}>
          Publications and uploads you've submitted, and their review status.
          Once approved, they appear below and on your public profile.
        </p>
        {!mySubmissions || mySubmissions.length === 0 ? (
          <p className={styles.hint}>You haven't submitted anything for review yet.</p>
        ) : (
          <ul className={styles.uploads}>
            {mySubmissions.map((s) => (
              <li key={`${s.kind}-${s.id}`} className={styles.pendingItem}>
                <div className={styles.pendingHead}>
                  <span className={styles.pendingTitle}>{s.title}</span>
                  <span className={styles.pendingMeta}>{kindLabel(s.kind)}</span>
                  <span className={`${styles.statusChip} ${statusClass(s.status)}`}>
                    {s.status.charAt(0).toUpperCase() + s.status.slice(1)}
                  </span>
                </div>
                {s.status === "rejected" && s.note && (
                  <p className={styles.reviewNote}>Reviewer note: {s.note}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section}>
        <h3 className={styles.h3}>Your publications</h3>
        <p className={styles.hint}>
          Publications linked to your profile — including ones you add above.
          They also appear on your public profile, in Publications, and in
          Analytics.
        </p>
        {!myPubs || myPubs.items.length === 0 ? (
          <p className={styles.hint}>No publications on your profile yet.</p>
        ) : (
          <ul className={styles.uploads}>
            {myPubs.items.map((p) => (
              <li key={p.publication_id} className={styles.upload}>
                <span>
                  {p.title}
                  {(p.source === "doi" || p.source === "manual") && (
                    <span className={styles.uploadDate}> · added by you</span>
                  )}
                </span>
                <span className={`mono ${styles.uploadDate}`}>
                  {p.publication_year}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <StudyPaper />

      <section className={styles.section}>
        <h3 className={styles.h3}>Upload a paper</h3>
        <p className={styles.hint}>
          A PDF of your own paper, up to 15 MB. It is attributed to you and
          added to the assistant's knowledge once an admin approves it — see
          "My submissions" above for status. For papers that are not yours,
          use "Study a paper" above.
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
