import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { clearToken, fetchMe, getToken } from "../api/auth";
import { PageHeader } from "../components/PageHeader";
import { Loader } from "../components/StateViews";
import { AdminPanel } from "../features/portal/AdminPanel";
import { AuthForms } from "../features/portal/AuthForms";
import { FacultyDashboard } from "../features/portal/FacultyDashboard";
import styles from "./Portal.module.css";

export default function Portal() {
  const queryClient = useQueryClient();
  // Auth is driven by React state, not read live from localStorage, so signing
  // in and out re-renders deterministically. (Reading getToken() at render time
  // let a stale `enabled: true` refetch the profile right after sign-out, so
  // the signed-in panel never went away.)
  const [token, setToken] = useState<string | null>(getToken());

  const { data: me, isLoading, refetch } = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    enabled: Boolean(token),
    retry: false,
  });

  const onSignedIn = () => {
    setToken(getToken()); // the token was just written by the auth form
    void refetch();
  };

  const signOut = () => {
    clearToken();
    setToken(null); // disables the profile query and flips back to signed-out
    queryClient.removeQueries({ queryKey: ["me"] });
  };

  const signedOut = !token || (!isLoading && !me);

  return (
    <>
      <PageHeader
        eyebrow="Faculty portal"
        title="Your research, your profile"
        description="Claim your researcher profile with your ORCID iD, sign in, and upload your papers so the assistant can answer questions about them."
      />
      <div className={`container ${styles.body}`}>
        {token && isLoading && <Loader />}
        {signedOut && <AuthForms onSignedIn={onSignedIn} />}
        {!signedOut && me?.role === "researcher" && (
          <FacultyDashboard me={me} onChanged={() => refetch()} onSignOut={signOut} />
        )}
        {!signedOut && me?.role === "admin" && <AdminPanel onSignOut={signOut} />}
      </div>
    </>
  );
}
