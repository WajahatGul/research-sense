import { useState, type FormEvent } from "react";

import { keepSearch, type AlertKind } from "../api/alerts";
import styles from "./KeepSearch.module.css";

/** "Email me new matches" for the search on screen.
 *
 * Shown only once there is a search or filter to follow. One field and one
 * press; the address confirms by email before anything else is sent.
 */
export function KeepSearch({
  kind,
  filters,
}: {
  kind: AlertKind;
  filters: Record<string, string | number | undefined>;
}) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState("");
  const [error, setError] = useState("");

  const active = Object.values(filters).some((v) => v !== undefined && v !== "");
  if (!active) return null;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setSending(true);
    setError("");
    try {
      const { status } = await keepSearch(email, kind, filters);
      setDone(
        status === "already on"
          ? "This address already follows this search."
          : `Almost done: open the message sent to ${email} and confirm. After that we write only when something new matches.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not keep this search.");
    } finally {
      setSending(false);
    }
  };

  if (done) return <p className={styles.done} role="status">{done}</p>;
  if (!open) {
    return (
      <button type="button" className={styles.trigger} onClick={() => setOpen(true)}>
        Email me new matches
      </button>
    );
  }
  return (
    <form className={styles.form} onSubmit={submit}>
      <label className={styles.label}>
        Your email
        <input
          className={styles.input}
          type="email"
          required
          autoFocus
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="name@example.org"
        />
      </label>
      <button type="submit" className={styles.save} disabled={sending}>
        {sending ? "Saving…" : "Keep this search"}
      </button>
      <button type="button" className={styles.cancel} onClick={() => setOpen(false)}>
        Cancel
      </button>
      {error && <p className={styles.error} role="alert">{error}</p>}
    </form>
  );
}
