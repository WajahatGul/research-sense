import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchOrganisation, type Organisation } from "../api/organisation";
import { SESSION_EVENT } from "../lib/session";

/** Used until the API answers, and if it cannot: neutral words that fit any
 * organisation, so nothing on screen names the wrong one. */
export const NEUTRAL: Organisation = {
  name: "",
  kind: "education",
  noun: "institution",
  people: "Researchers",
  unit: "Department",
  site: "Campus",
  document_types: [],
};

/** The organisation being viewed. Signing in to a workspace changes whose
 * data is served, so the answer is refetched when the session changes. */
export function useOrganisation(): Organisation {
  const client = useQueryClient();
  const { data } = useQuery({
    queryKey: ["organisation"],
    queryFn: fetchOrganisation,
    staleTime: Infinity,
  });

  useEffect(() => {
    const refresh = () => client.invalidateQueries({ queryKey: ["organisation"] });
    window.addEventListener(SESSION_EVENT, refresh);
    return () => window.removeEventListener(SESSION_EVENT, refresh);
  }, [client]);

  return data ?? NEUTRAL;
}
