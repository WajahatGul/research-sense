import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { getToken } from "../api/auth";
import { fetchLibrary, removeLibraryPaper } from "../api/library";
import { PageHeader } from "../components/PageHeader";
import { Loader, ErrorState } from "../components/StateViews";
import styles from "./Library.module.css";

export default function Library() {
  const queryClient = useQueryClient();
  const [error, setError] = useState("");
  const signedIn = Boolean(getToken());

  const { data, isLoading, isError } = useQuery({
    queryKey: ["library"],
    queryFn: fetchLibrary,
  });

  const remove = async (filename: string) => {
    setError("");
    try {
      await removeLibraryPaper(filename);
      void queryClient.invalidateQueries({ queryKey: ["library"] });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not remove the paper");
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Reading room"
        title="Library"
        description="Papers added for study — the assistant has read their full text and can answer questions about them. Library papers are not attributed to any researcher's profile."
      />

      <div className={`container ${styles.body}`}>
        {isLoading && <Loader />}
        {isError && <ErrorState />}
        {error && <p className={styles.error}>{error}</p>}

        {data && data.length === 0 && (
          <div className={styles.empty}>
            <p>The library is empty.</p>
            <p className={styles.emptyHint}>
              Faculty members can add any paper by DOI or PDF from the{" "}
              <Link to="/portal" className={styles.link}>Portal</Link>{" "}
              ("Study a paper").
            </p>
          </div>
        )}

        {data && data.length > 0 && (
          <ul className={styles.list}>
            {data.map((p) => (
              <li key={p.filename} className={styles.card}>
                <div className={styles.cardMain}>
                  <p className={styles.title}>{p.title}</p>
                  <p className={styles.meta}>
                    {p.year ?? "n.d."}
                    {p.doi && (
                      <>
                        {" · "}
                        <a href={`https://doi.org/${p.doi}`} target="_blank"
                           rel="noreferrer" className={styles.link}>
                          doi:{p.doi}
                        </a>
                      </>
                    )}
                    {" · "}
                    {p.chunks} indexed passages
                    {p.added_at && ` · added ${p.added_at.slice(0, 10)}`}
                  </p>
                </div>
                <div className={styles.actions}>
                  <Link
                    to={`/ask?q=${encodeURIComponent(`Summarize the paper "${p.title}"`)}`}
                    className={styles.ask}
                  >
                    Ask about it
                  </Link>
                  {signedIn && (
                    <button className={styles.remove}
                            onClick={() => void remove(p.filename)}>
                      Remove
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
