import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getToken } from "../../api/auth";
import styles from "./portal.module.css";

interface Coauthor {
  researcher_id: number;
  full_name: string;
  department: string;
  email: string | null;
  joint_papers: number;
  claim_link: string;
}

async function fetchCoauthors(): Promise<{ inviter: string; coauthors: Coauthor[] }> {
  const res = await fetch("/api/invitations/coauthors", {
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  if (!res.ok) throw new Error("Could not load co-authors");
  return res.json();
}

function inviteMail(c: Coauthor, inviter: string): string {
  const subject = "Your research profile on ResearchSense";
  const body =
    `Dear ${c.full_name},\n\n` +
    `We have ${c.joint_papers} paper${c.joint_papers === 1 ? "" : "s"} together on ResearchSense, ` +
    "where our institution's research is searchable by people looking for experts " +
    "and collaborators. Your profile is there but not claimed yet. Claiming it lets " +
    "you correct your papers and add missing ones:\n\n" +
    `${c.claim_link}\n\n` +
    `Best regards,\n${inviter}`;
  return `mailto:${c.email ?? ""}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

/** Bring in the people you publish with.
 *
 * Co-authors on the directory who have not claimed their profile, most joint
 * papers first. The invitation is sent from the researcher's own mail
 * program, in their name, with a link that opens the claim form already set
 * to the co-author's profile.
 */
export function InviteCoauthors() {
  const [copied, setCopied] = useState<number | null>(null);
  const { data } = useQuery({ queryKey: ["invite-coauthors"], queryFn: fetchCoauthors });
  if (!data || data.coauthors.length === 0) return null;

  const copy = async (c: Coauthor) => {
    try {
      await navigator.clipboard.writeText(c.claim_link);
      setCopied(c.researcher_id);
    } catch {
      setCopied(null);
    }
  };

  return (
    <section className={styles.section}>
      <h3 className={styles.h3}>Invite your co-authors</h3>
      <p className={styles.hint}>
        People you publish with who have not claimed their profile yet. An invitation
        from you opens their claim form ready to go.
      </p>
      <ul className={styles.uploads}>
        {data.coauthors.map((c) => (
          <li key={c.researcher_id} className={styles.upload}>
            <span>
              <Link to={`/researchers/${c.researcher_id}`} className={styles.link}>
                {c.full_name}
              </Link>
              <span className={styles.uploadDate}>
                {" "}· {c.joint_papers} joint paper{c.joint_papers === 1 ? "" : "s"}
                {c.department ? ` · ${c.department}` : ""}
              </span>
            </span>
            <span className={styles.inviteActions}>
              {c.email && (
                <a className={styles.secondary} href={inviteMail(c, data.inviter)}>
                  Invite by email
                </a>
              )}
              <button type="button" className={styles.secondary} onClick={() => copy(c)}>
                {copied === c.researcher_id ? "Link copied" : "Copy invite link"}
              </button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
