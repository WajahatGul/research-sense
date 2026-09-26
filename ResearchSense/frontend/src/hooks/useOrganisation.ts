import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { fetchOrganisation, type Organisation } from "../api/organisation";
import { plural } from "../config";
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

export interface Terms {
  site: string; // "campus"
  sites: string; // "campuses"
  Site: string; // "Campus"
  Sites: string; // "Campuses"
  unit: string; // "department"
  units: string; // "departments"
  people: string; // "researchers"
  noun: string; // "institution"
}

/** The organisation's words, ready for sentences and headings, so a
 * company reads "sites" and "teams" where a university reads "campuses"
 * and "departments". */
export function useTerms(): Terms {
  const org = useOrganisation();
  const Sites = plural(org.site);
  return {
    site: org.site.toLowerCase(),
    sites: Sites.toLowerCase(),
    Site: org.site,
    Sites,
    unit: org.unit.toLowerCase(),
    units: plural(org.unit).toLowerCase(),
    people: org.people.toLowerCase(),
    noun: org.noun,
  };
}
