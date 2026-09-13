import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { fetchStats } from "../api/stats";
import { PageHeader } from "../components/PageHeader";
import { useInstitution } from "../hooks/useInstitution";
import styles from "./Guide.module.css";

/** The page to send someone who has never seen ResearchSense.
 *
 * Every other page answers a question the visitor already knew to ask. This
 * one explains what the product is, what it can and cannot tell them, and
 * where its numbers come from — including the limits, because a research
 * portal that overstates its coverage is worse than one that admits it.
 */
export default function Guide() {
  const institution = useInstitution();
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: fetchStats });

  const n = (value?: number) => (value ?? 0).toLocaleString();

  return (
    <>
      <PageHeader
        eyebrow="Documentation"
        title="Get started"
        description={`ResearchSense turns a university's scattered research record into one place you can search, read and ask questions of. This page explains what is inside, how to use it, and how far it can be trusted.`}
      />

      <div className={`container ${styles.body}`}>
        {/* What is actually in here, right now — not a claim, a count. */}
        <section className={styles.figures} aria-label="What is indexed">
          <div className={styles.figure}>
            <span className={styles.figureNum}>{n(stats?.researchers)}</span>
            <span className={styles.figureLabel}>faculty profiles</span>
          </div>
          <div className={styles.figure}>
            <span className={styles.figureNum}>{n(stats?.publications)}</span>
            <span className={styles.figureLabel}>publications</span>
          </div>
          <div className={styles.figure}>
            <span className={styles.figureNum}>{n(stats?.topics)}</span>
            <span className={styles.figureLabel}>research areas</span>
          </div>
          <div className={styles.figure}>
            <span className={styles.figureNum}>{n(stats?.campuses)}</span>
            <span className={styles.figureLabel}>campuses</span>
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.h2}>Three ways in</h2>
          <p className={styles.lead}>
            Most people never need an account. Signing in only matters when you
            want to change what the portal says about you.
          </p>

          <div className={styles.paths}>
            <article className={styles.path}>
              <span className={styles.pathStep}>01</span>
              <h3 className={styles.h3}>Just look around</h3>
              <p className={styles.copy}>
                Everything is readable without signing in — every profile,
                every paper, the analytics, and the assistant. Nothing is held
                back behind a login.
              </p>
              <Link className={styles.pathLink} to="/researchers">
                Browse the researchers →
              </Link>
            </article>

            <article className={styles.path}>
              <span className={styles.pathStep}>02</span>
              <h3 className={styles.h3}>Claim your profile</h3>
              <p className={styles.copy}>
                If you research at {institution}, your profile is probably
                already here. Claiming it lets you correct your details and add
                papers we have not found, so the assistant can answer about
                them.
              </p>
              <Link className={styles.pathLink} to="/portal">
                Find your profile →
              </Link>
            </article>

            <article className={styles.path}>
              <span className={styles.pathStep}>03</span>
              <h3 className={styles.h3}>Bring your own university</h3>
              <p className={styles.copy}>
                From somewhere else? Create an account and you get a private
                space that starts empty. Paste a CV, review what was read from
                it, and your portal is built from your own record —
                {" "}{institution}'s data never appears in it.
              </p>
              <Link className={styles.pathLink} to="/portal">
                Create an account →
              </Link>
            </article>
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.h2}>What you can do here</h2>
          <div className={styles.features}>
            <article className={styles.feature}>
              <h3 className={styles.h3}>Find people by what they work on</h3>
              <p className={styles.copy}>
                Filter the directory by campus, department and rank, or search
                a topic and see who publishes in it. Research areas are derived
                from the papers themselves, not from a form somebody filled in
                once.
              </p>
            </article>
            <article className={styles.feature}>
              <h3 className={styles.h3}>Read the output</h3>
              <p className={styles.copy}>
                Publications are listed with their venue, year, citation count
                and a link to the paper. Filter by date range, department or
                type to see a slice of the record rather than all of it.
              </p>
            </article>
            <article className={styles.feature}>
              <h3 className={styles.h3}>See the shape of the research</h3>
              <p className={styles.copy}>
                Analytics charts publication and citation trends per campus,
                the leading venues, and how often campuses co-author. It is
                computed from the indexed records, so it moves when they do.
              </p>
            </article>
            <article className={styles.feature}>
              <h3 className={styles.h3}>Find a collaborator</h3>
              <p className={styles.copy}>
                Pick a researcher and the collaboration finder shows proven
                past co-authors first, then people who share the most research
                areas — the ones a first email is most likely to land with.
              </p>
            </article>
            <article className={styles.feature}>
              <h3 className={styles.h3}>Ask in plain English</h3>
              <p className={styles.copy}>
                "Who works on machine learning in Karachi?" "What has Dr Khan
                published?" The assistant answers from the indexed records and
                cites what it used, so you can check it.
              </p>
            </article>
            <article className={styles.feature}>
              <h3 className={styles.h3}>Study a specific paper</h3>
              <p className={styles.copy}>
                Papers added to the library are read in full, so the assistant
                can summarise them and answer detailed questions about their
                method and findings rather than just their title.
              </p>
            </article>
          </div>
        </section>

        {/* The part that actually distinguishes this from a search box. */}
        <section className={styles.section}>
          <h2 className={styles.h2}>How the assistant answers</h2>
          <p className={styles.lead}>
            It is not a chatbot with opinions. It can only repeat what is in
            the records, and it is built to say so when they do not cover your
            question.
          </p>
          <ol className={styles.steps}>
            <li className={styles.step}>
              <strong>It searches before it speaks.</strong> Your question is
              matched against the indexed profiles, publications, research
              areas and papers. Nothing is generated until something relevant
              is found.
            </li>
            <li className={styles.step}>
              <strong>It answers only from what it found.</strong> The records
              retrieved are the only material it is allowed to use. Ask it the
              capital of France and it will decline — not because it does not
              know, but because that is not what it is for.
            </li>
            <li className={styles.step}>
              <strong>It shows its sources.</strong> Answers carry the profiles
              and papers they came from, so you can open them and judge for
              yourself.
            </li>
            <li className={styles.step}>
              <strong>It admits the edges.</strong> Where the evidence is thin
              it answers and says the coverage is limited. Where there is
              nothing, it says so and points you somewhere better, rather than
              inventing a plausible name.
            </li>
          </ol>
          <Link className={styles.cta} to="/ask">
            Try the assistant
          </Link>
        </section>

        <section className={styles.section}>
          <h2 className={styles.h2}>Where the data comes from</h2>
          <div className={styles.twoUp}>
            <div>
              <h3 className={styles.h3}>Two kinds of profile</h3>
              <p className={styles.copy}>
                <strong>Directory profiles</strong> come from the faculty
                listing and carry a department, campus, biography and
                education. They are what you see when browsing.
              </p>
              <p className={styles.copy}>
                <strong>Publication-only profiles</strong> are authors who
                appear on {institution} papers without a directory entry.
                OpenAlex knows their name and their work but nothing else, so
                they do not clutter the directory — search their name and you
                will find them.
                {!!stats?.researchers_extended && (
                  <>
                    {" "}
                    There are {n(stats.researchers_extended)} of them.
                  </>
                )}
              </p>
            </div>
            <div>
              <h3 className={styles.h3}>Honest limits</h3>
              <p className={styles.copy}>
                Publications are matched from{" "}
                <a
                  className={styles.extLink}
                  href="https://openalex.org"
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  OpenAlex
                </a>
                , an open catalogue of scholarly work. Matching an author to a
                paper is imperfect, and no catalogue is complete, so counts
                here are a floor and not a total.
              </p>
              <p className={styles.copy}>
                That is why coverage notes sit on the directory, the
                publications list and the analytics. They are not disclaimers —
                they tell you exactly how much of the record you are looking
                at, which is the difference between a figure you can cite and
                one you cannot.
              </p>
            </div>
          </div>
        </section>

        <section className={styles.section}>
          <h2 className={styles.h2}>Questions</h2>
          <dl className={styles.faq}>
            <dt className={styles.q}>Do I need an account to read anything?</dt>
            <dd className={styles.a}>
              No. Every page is public. An account only lets you manage your own
              profile or build a portal for a different university.
            </dd>

            <dt className={styles.q}>My profile is wrong. Can I fix it?</dt>
            <dd className={styles.a}>
              Claim it from the portal and you can correct your details and
              submit papers we missed. Submitted papers are reviewed before they
              appear, so the public record stays trustworthy.
            </dd>

            <dt className={styles.q}>Why is my paper missing?</dt>
            <dd className={styles.a}>
              Most likely OpenAlex does not link it to your institution, or your
              name is spelled differently on it. Claim your profile and add it
              by DOI.
            </dd>

            <dt className={styles.q}>
              Someone else claimed my profile. What now?
            </dt>
            <dd className={styles.a}>
              A profile can only be claimed once, and claiming requires an ORCID
              iD that matches. If one was taken in error an administrator can
              release it.
            </dd>

            <dt className={styles.q}>Is my data shared with other universities?</dt>
            <dd className={styles.a}>
              No. An institution's workspace is separate: its records are never
              mixed with {institution}'s, and its assistant only ever reads its
              own data.
            </dd>

            <dt className={styles.q}>How current is this?</dt>
            <dd className={styles.a}>
              The record is refreshed periodically rather than live. Anything
              you add yourself appears immediately.
            </dd>
          </dl>
        </section>

        <section className={styles.closing}>
          <h2 className={styles.closingTitle}>Start anywhere</h2>
          <p className={styles.closingCopy}>
            Nothing here needs setting up. Open the directory, ask the
            assistant a question, or find your own profile.
          </p>
          <div className={styles.closingLinks}>
            <Link className={styles.cta} to="/researchers">
              Browse researchers
            </Link>
            <Link className={styles.ctaGhost} to="/ask">
              Ask the assistant
            </Link>
            <Link className={styles.ctaGhost} to="/portal">
              Find your profile
            </Link>
          </div>
        </section>
      </div>
    </>
  );
}
