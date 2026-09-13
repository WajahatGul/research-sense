import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  clearToken,
  fetchMe,
  getToken,
  setToken as storeToken,
} from "../api/auth";
import { getWorkspaceSession, type WorkspaceSession } from "../api/workspace";
import { PageHeader } from "../components/PageHeader";
import { Loader } from "../components/StateViews";
import { AdminPanel } from "../features/portal/AdminPanel";
import { AuthForms } from "../features/portal/AuthForms";
import { FacultyDashboard } from "../features/portal/FacultyDashboard";
import { WorkspaceDashboard } from "../features/portal/WorkspaceDashboard";
import styles from "./Portal.module.css";

export default function Portal() {
  const queryClient = useQueryClient();
  // Auth is driven by React state, not read live from localStorage, so signing
  // in and out re-renders deterministically. (Reading getToken() at render time
  // let a stale `enabled: true` refetch the profile right after sign-out, so
  // the signed-in panel never went away.)
  const [token, setToken] = useState<string | null>(getToken());
  // An institution workspace session is separate from the Bahria ORCID login:
  // it has its own dashboard for building a profile from a CV.
  const [workspace, setWorkspace] = useState<WorkspaceSession | null>(
    getWorkspaceSession(),
  );

  const { data: me, isLoading, refetch } = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    // A workspace session is not an ORCID profile, so skip the profile lookup.
    enabled: Boolean(token) && !workspace,
    retry: false,
  });

  // Returning from orcid.org. The round trip is a full page load, not a
  // fetch, so the outcome arrives as a query parameter; consume it once and
  // clear it so a refresh does not replay a stale result.
  const [searchParams, setSearchParams] = useSearchParams();
  const [orcidError, setOrcidError] = useState("");
  /* eslint-disable react-hooks/set-state-in-effect --
     A one-time read of the OAuth return on mount, not a render loop: the
     parameters are cleared in the same pass, so this cannot run again. */
  useEffect(() => {
    const granted = searchParams.get("orcid_token");
    const failed = searchParams.get("orcid_error");
    if (!granted && !failed) return;
    if (granted) {
      storeToken(granted);
      setToken(granted);
    }
    if (failed) setOrcidError(failed);
    setSearchParams({}, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  /* eslint-enable react-hooks/set-state-in-effect */

  const onSignedIn = () => {
    setToken(getToken()); // the token was just written by the auth form
    setWorkspace(getWorkspaceSession());
    void refetch();
  };

  const signOut = () => {
    clearToken();
    setToken(null); // disables the profile query and flips back to signed-out
    setWorkspace(null);
    queryClient.removeQueries({ queryKey: ["me"] });
  };

  const signedOut = !workspace && (!token || (!isLoading && !me));

  return (
    <>
      {/* The portal serves two different people now — a researcher here and
          an institution setting up its own space — so the heading cannot
          promise only the first. */}
      <PageHeader
        eyebrow="Sign in"
        title="Your research, your profile"
        description="Claim the profile that is already here, or create a private workspace for your own university. Reading the portal needs no account."
      />
      <div className={`container ${styles.body}`}>
        {orcidError && (
          <p className={styles.orcidError} role="alert">
            {orcidError}
          </p>
        )}
        {token && !workspace && isLoading && <Loader />}
        {signedOut && <AuthForms onSignedIn={onSignedIn} />}
        {workspace && (
          <WorkspaceDashboard
            session={workspace}
            onSignOut={signOut}
            onChanged={() => queryClient.invalidateQueries()}
          />
        )}
        {!signedOut && !workspace && me?.role === "researcher" && (
          <FacultyDashboard me={me} onChanged={() => refetch()} onSignOut={signOut} />
        )}
        {!signedOut && !workspace && me?.role === "admin" && (
          <AdminPanel onSignOut={signOut} />
        )}
      </div>
    </>
  );
}
