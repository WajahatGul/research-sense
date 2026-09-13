import { get, post } from "./client";

const TOKEN_KEY = "rs_token";

export interface TokenResponse {
  token: string;
  role: "researcher" | "admin";
  researcher_id: number | null;
  full_name: string | null;
}

export interface UploadedPaper {
  title: string;
  filename: string;
  uploaded_at: string;
}

export interface Me {
  role: "researcher" | "admin";
  orcid_id: string | null;
  researcher_id: number | null;
  full_name: string | null;
  uploads: UploadedPaper[];
}

export interface ClaimedAccount {
  orcid_id: string;
  researcher_id: number;
  full_name: string;
  active: boolean;
  created_at: string;
}

// --- token storage ---
export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token: string) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

const authHeaders = () => ({ Authorization: `Bearer ${getToken()}` });

// --- endpoints ---
export const claimProfile = (researcher_id: number, orcid_id: string, password: string) =>
  post<TokenResponse>("/api/auth/claim", { researcher_id, orcid_id, password });

export const login = (orcid_id: string, password: string) =>
  post<TokenResponse>("/api/auth/login", { orcid_id, password });

export const adminLogin = (username: string, password: string) =>
  post<TokenResponse>("/api/auth/admin-login", { username, password });

export const fetchClaimedIds = () => get<number[]>("/api/auth/claimed");

export async function fetchMe(): Promise<Me> {
  const res = await fetch("/api/auth/me", { headers: authHeaders() });
  if (!res.ok) throw new Error("Not signed in");
  return res.json();
}

export async function uploadPaper(title: string, file: File) {
  const body = new FormData();
  body.append("title", title);
  body.append("file", file);
  const res = await fetch("/api/papers/upload", {
    method: "POST",
    headers: authHeaders(),
    body,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Upload failed");
  return data as { status: string; submission_id: number; message: string };
}

// --- publication submission (DOI-based + manual, proposal ingestion) ---

export interface DoiPreview {
  doi: string;
  title: string;
  authors: string[];
  publication_year: number;
  journal_name: string;
  publication_type: string;
  citation_count: number;
  abstract: string;
  concepts: string[];
  topics: string[];
  duplicate: boolean;
  duplicate_of: string | null;
  authorship_ok: boolean;
  authorship_message: string | null;
}

export interface SubmissionResult {
  publication_id: number | null;
  title: string;
  publication_year: number;
  journal_name: string;
  message: string;
}

async function authedPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Request failed");
  return data as T;
}

export const previewDoi = (doi: string) =>
  authedPost<DoiPreview>("/api/papers/doi/preview", { doi });

export const submitDoi = (doi: string) =>
  authedPost<SubmissionResult>("/api/papers/doi/submit", { doi });

export const submitManualPublication = (fields: {
  title: string;
  journal_name: string;
  publication_year: number;
  publication_type: string;
}) => authedPost<SubmissionResult>("/api/papers/manual", fields);

// --- library: study any paper (no attribution) ---

export interface StudyResult {
  title: string;
  chunks_added: number;
  message: string;
}

export const studyDoi = (doi: string) =>
  authedPost<StudyResult>("/api/papers/study/doi", { doi });

export async function studyUpload(title: string, file: File) {
  const body = new FormData();
  body.append("title", title);
  body.append("file", file);
  const res = await fetch("/api/papers/study/upload", {
    method: "POST",
    headers: authHeaders(),
    body,
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Upload failed");
  return data as StudyResult;
}

// --- admin approval queue / submission status ---

export interface PendingPaper {
  id: number;
  kind: "publication" | "upload";
  researcher_id: number;
  title: string;
  submitted_at: string;
  record: Record<string, unknown>;
}

export interface MySubmission {
  id: number;
  kind: string;
  title: string;
  status: "pending" | "approved" | "rejected";
  submitted_at: string;
  reviewed_at: string | null;
  note: string | null;
}

export async function fetchPendingPapers(): Promise<PendingPaper[]> {
  const res = await fetch("/api/admin/papers/pending", { headers: authHeaders() });
  if (!res.ok) throw new Error("Admin access required");
  return res.json();
}

export const approvePaper = (id: number) =>
  authedPost<{ status: string }>(`/api/admin/papers/${id}/approve`, {});

export const rejectPaper = (id: number, note: string) =>
  authedPost<{ status: string }>(`/api/admin/papers/${id}/reject`, { note });

export async function fetchMySubmissions(): Promise<MySubmission[]> {
  const res = await fetch("/api/papers/mine", { headers: authHeaders() });
  if (!res.ok) throw new Error("Could not load submissions");
  return res.json();
}

export async function fetchAdminAccounts(): Promise<ClaimedAccount[]> {
  const res = await fetch("/api/admin/accounts", { headers: authHeaders() });
  if (!res.ok) throw new Error("Admin access required");
  return res.json();
}

export async function setAccountActive(orcid_id: string, active: boolean) {
  const res = await fetch(
    `/api/admin/accounts/${orcid_id}/active?active=${active}`,
    { method: "POST", headers: authHeaders() });
  if (!res.ok) throw new Error("Could not update account");
  return res.json();
}

export async function fetchRefreshStatus() {
  const res = await fetch("/api/admin/refresh", { headers: authHeaders() });
  if (!res.ok) throw new Error("Admin access required");
  return res.json() as Promise<{ last_refresh: { finished_at: string } | null; due: boolean }>;
}

export async function triggerRefresh() {
  const res = await fetch("/api/admin/refresh", {
    method: "POST", headers: authHeaders() });
  if (!res.ok) throw new Error("Could not start refresh");
  return res.json();
}

// --- Sign in with ORCID -----------------------------------------------------
// Proof that an iD belongs to the claimant, rather than the weaker check that
// the name on its public record matches. Absent a configured ORCID client the
// portal falls back to that name check and says so.

/** Whether this deployment can offer "Verify with ORCID". */
export const orcidSignInAvailable = () =>
  get<boolean>("/api/auth/orcid/available");

/** Hand the chosen profile and password to the server, get the ORCID URL. */
export const beginOrcidClaim = (researcher_id: number, password: string) =>
  post<{ authorize_url: string }>("/api/auth/orcid/begin", {
    researcher_id,
    password,
  });
