import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { confirmAlert, stopAlert } from "../api/alerts";
import { PageHeader } from "../components/PageHeader";
import styles from "./Alerts.module.css";

/** Where the links in alert emails land.
 *
 * The change waits for a press rather than happening on load: mail
 * scanners open links in messages, and would otherwise confirm or stop
 * alerts nobody chose.
 */
export default function Alerts() {
  const [params] = useSearchParams();
  const confirmToken = params.get("confirm");
  const stopToken = params.get("stop");
  const token = confirmToken ?? stopToken;
  const [result, setResult] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const act = async () => {
    if (!token) return;
    setBusy(true);
    setError("");
    try {
      if (confirmToken) {
        const r = await confirmAlert(confirmToken);
        setResult(`Confirmed. We will email you when something new matches ${r.search}.`);
      } else {
        const r = await stopAlert(token);
        setResult(`Stopped. You will not hear about ${r.search} again.`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Alerts"
        title={confirmToken ? "Confirm your alert" : "Stop an alert"}
        description="Saved searches that email you only when something new matches."
      />
      <div className={`container ${styles.body}`}>
        {!token && (
          <p>
            This page opens from the links in alert emails. To keep a search, search on{" "}
            <Link to="/publications">Publications</Link> or <Link to="/researchers">Researchers</Link>{" "}
            and choose “Email me new matches”.
          </p>
        )}
        {token && !result && (
          <button type="button" className={styles.action} onClick={act} disabled={busy}>
            {confirmToken ? "Confirm alert" : "Stop this alert"}
          </button>
        )}
        {result && <p role="status" className={styles.result}>{result}</p>}
        {error && <p role="alert" className={styles.error}>{error}</p>}
      </div>
    </>
  );
}
