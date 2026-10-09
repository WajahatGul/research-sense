import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getToken } from "../../api/auth";
import styles from "./portal.module.css";

interface Message {
  id: number;
  at: string;
  to_addr: string;
  subject: string;
  body: string;
  reason: string;
  status: string;
  error: string | null;
}

async function fetchOutbox(): Promise<{ messages: Message[]; mail_server: boolean }> {
  const res = await fetch("/api/admin/outbox", { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error("Could not load messages");
  return res.json();
}

const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });

/** What people were told about decisions on their claims, papers and corrections.
 *
 * Every message is kept here. Without a mail server nothing leaves the
 * site, so the admin can open any message in their own mail program and
 * send it on.
 */
export function Outbox() {
  const [open, setOpen] = useState<number | null>(null);
  // Alert emails go out in the background just after an approval, so a
  // refetch on the decision alone can miss them.
  const { data } = useQuery({
    queryKey: ["admin-outbox"],
    queryFn: fetchOutbox,
    refetchInterval: 15_000,
  });
  if (!data) return null;

  return (
    <section className={styles.section}>
      <h3 className={styles.h3}>Messages to researchers</h3>
      <p className={styles.hint}>
        Each decision on a claim, paper or correction writes to the researcher's directory
        address.{" "}
        {data.mail_server
          ? "A mail server is set, so these are sent automatically."
          : "No mail server is set (SMTP_HOST), so nothing is sent automatically: use “Send from my mail” to pass one on."}
      </p>
      {data.messages.length === 0 ? (
        <p className={styles.hint}>No messages yet.</p>
      ) : (
        <ul className={styles.uploads}>
          {data.messages.map((m) => (
            <li key={m.id} className={styles.outboxItem}>
              <div className={styles.upload}>
                <button
                  type="button"
                  className={styles.linkButton}
                  aria-expanded={open === m.id}
                  onClick={() => setOpen(open === m.id ? null : m.id)}
                >
                  {m.subject}
                </button>
                <span className={styles.uploadDate}>
                  {m.to_addr} · {when(m.at)} · {m.status}
                  {m.error ? ` (${m.error})` : ""}
                </span>
              </div>
              {open === m.id && (
                <>
                  <pre className={styles.outboxBody}>{m.body}</pre>
                  {m.status !== "sent" && (
                    <a
                      className={styles.secondary}
                      href={`mailto:${m.to_addr}?subject=${encodeURIComponent(m.subject)}&body=${encodeURIComponent(m.body)}`}
                    >
                      Send from my mail
                    </a>
                  )}
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
