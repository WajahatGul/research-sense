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
  return data as { status: string; chunks_added: number; message: string };
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
