import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { clearToken, fetchMe, getToken } from "../api/auth";
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
      <PageHeader
        eyebrow="Faculty portal"
        title="Your research, your profile"
        description="Claim your researcher profile with your ORCID iD, sign in, and upload your papers so the assistant can answer questions about them."
      />
      <div className={`container ${styles.body}`}>
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
