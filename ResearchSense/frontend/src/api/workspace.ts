import { announceSession, forgetChat } from "../lib/session";
import { post } from "./client";

export interface WorkspaceSession {
  token: string;
  role: string;
  workspace_id: string;
  institution_name: string;
  full_name: string;
  researcher_id: number;
}

export interface CvPublication {
  title: string;
  publication_year: number | null;
  journal_name: string;
  doi: string | null;
}

/** The editable review form: what was read from the CV. Nothing is stored on
 *  the server until this comes back from `applyCv`. */
export interface CvDraft {
  full_name: string;
  designation: string;
  department: string;
  institution: string;
  education: string;
  profile_bio: string;
  research_areas: string[];
  publications: CvPublication[];
}

export interface CvApplyResult {
  publications_added: number;
  research_areas: string[];
  message: string;
}

// --- session storage -------------------------------------------------------
// The workspace session is kept alongside the shared token so every API call
// is scoped to this institution, and the portal knows to show its dashboard.
const WS_KEY = "rs_workspace";

export function saveWorkspaceSession(session: WorkspaceSession): void {
  try {
    localStorage.setItem("rs_token", session.token);
    localStorage.setItem(WS_KEY, JSON.stringify(session));
  } catch {
    /* storage unavailable: the session lasts for this page only */
  }
  announceSession();
}

export function getWorkspaceSession(): WorkspaceSession | null {
  try {
    const raw = localStorage.getItem(WS_KEY);
    return raw ? (JSON.parse(raw) as WorkspaceSession) : null;
  } catch {
    return null;
  }
}

export function clearWorkspaceSession(): void {
  // The assistant's conversation goes with the session: it holds this
  // institution's own research, and the next person on this browser is a
  // different tenant (often the anonymous demo).
  forgetChat(getWorkspaceSession()?.workspace_id);
  try {
    localStorage.removeItem(WS_KEY);
    localStorage.removeItem("rs_token");
  } catch {
    /* ignore */
  }
  announceSession();
}

export const signUpWorkspace = (fields: {
  email: string;
  password: string;
  institution_name: string;
  full_name: string;
  department: string;
  campus: string;
}) => post<WorkspaceSession>("/api/workspace/signup", fields);

export const loginWorkspace = (email: string, password: string) =>
  post<WorkspaceSession>("/api/workspace/login", { email, password });

export const parseCv = (text: string) =>
  post<CvDraft>("/api/workspace/cv/parse", { text });

export const applyCv = (draft: CvDraft) =>
  post<CvApplyResult>("/api/workspace/cv/apply", draft);

export const addWorkspaceDoi = (doi: string) =>
  post<CvApplyResult>("/api/workspace/publications/doi", { doi });
