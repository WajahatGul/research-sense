import { useEffect, useState } from "react";

import { getWorkspaceSession } from "../api/workspace";
import { INSTITUTION_NAME } from "../config";
import { SESSION_EVENT } from "../lib/session";

/** Which institution the visitor is currently looking at.
 *
 * The build-time name brands the deployment (the demo corpus, Bahria here).
 * An institution signed in to its own workspace is looking at its own data, so
 * the product must say its name instead — otherwise the footer thanks Bahria
 * on a page full of someone else's research.
 */
export function useInstitution(): string {
  const read = () => getWorkspaceSession()?.institution_name || INSTITUTION_NAME;
  const [name, setName] = useState<string>(read);

  useEffect(() => {
    const onSession = () => setName(read());
    window.addEventListener(SESSION_EVENT, onSession);
    return () => window.removeEventListener(SESSION_EVENT, onSession);
  }, []);

  return name;
}
