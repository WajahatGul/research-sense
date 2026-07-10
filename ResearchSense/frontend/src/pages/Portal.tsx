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

  const { data: me, isLoading, refetch } = useQuery({
    queryKey: ["me"],
    queryFn: fetchMe,
    enabled: Boolean(getToken()),
    retry: false,
  });

  const signOut = () => {
    clearToken();
    queryClient.removeQueries({ queryKey: ["me"] });
    queryClient.invalidateQueries();
  };

  const signedOut = !getToken() || (!isLoading && !me);

  return (
    <>
      <PageHeader
        eyebrow="Faculty portal"
        title="Your research, your profile"
        description="Claim your researcher profile with your ORCID iD, sign in, and upload your papers so the assistant can answer questions about them."
      />
      <div className={`container ${styles.body}`}>
        {getToken() && isLoading && <Loader />}
        {signedOut && <AuthForms onSignedIn={() => refetch()} />}
        {me?.role === "researcher" && (
          <FacultyDashboard me={me} onChanged={() => refetch()} onSignOut={signOut} />
        )}
        {me?.role === "admin" && <AdminPanel onSignOut={signOut} />}
      </div>
    </>
  );
}
