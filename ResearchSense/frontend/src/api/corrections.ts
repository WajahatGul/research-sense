import { getToken } from "./auth";

// Correcting who wrote what: see backend app/services/identity_service.py.

export interface Suggestion {
  researcher_id: number;
  profile_name: string;
  openalex_id: string;
  other_name: string;
  papers: { publication_id: number; title: string; year: number | null }[];
  paper_count: number;
  shared_coauthors: number;
  shared_areas: string[];
  score: number;
}

export interface Correction {
  id: number;
  kind: "not_author" | "same_person";
  status: "pending" | "approved" | "rejected";
  researcher_id: number;
  profile_name: string;
  paper_title: string | null;
  paper_doi: string | null;
  other_name: string | null;
  other_openalex_id: string | null;
  note: string;
  raised_by: string;
  submitted_at: string;
  review_note: string | null;
  evidence?: unknown;
}

const headers = () => ({
  "Content-Type": "application/json",
  Authorization: `Bearer ${getToken()}`,
});

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method,
    headers: headers(),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data as T;
}

export const fetchMyCorrections = () =>
  send<{ corrections: Correction[]; suggestions: Suggestion[] }>("GET", "/api/corrections/mine");

export const reportNotMine = (publication_id: number, note: string) =>
  send<{ message: string }>("POST", "/api/corrections/not-mine", { publication_id, note });

export const confirmSamePerson = (openalex_id: string) =>
  send<{ message: string }>("POST", "/api/corrections/same-person", { openalex_id });

export const dismissSuggestion = (openalex_id: string) =>
  send<{ status: string }>("POST", "/api/corrections/not-me", { openalex_id });

// --- administrators ---
export const fetchPendingCorrections = () => send<Correction[]>("GET", "/api/admin/corrections");

export const approveCorrection = (id: number) =>
  send<{ status: string }>("POST", `/api/admin/corrections/${id}/approve`, {});

export const rejectCorrection = (id: number, note: string) =>
  send<{ status: string }>("POST", `/api/admin/corrections/${id}/reject`, { note });

export const fetchIdentityCandidates = (limit = 20) =>
  send<Suggestion[]>("GET", `/api/admin/corrections/candidates?limit=${limit}`);

export const decideCandidate = (researcher_id: number, openalex_id: string, same: boolean) =>
  send<{ status: string }>("POST", "/api/admin/corrections/candidates/decide", {
    researcher_id,
    openalex_id,
    same,
  });
