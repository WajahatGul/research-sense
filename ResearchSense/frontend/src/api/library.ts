import { get } from "./client";
import { getToken } from "./auth";

export interface LibraryEntry {
  doi: string | null;
  title: string;
  year: number | string | null;
  filename: string;
  chunks: number;
  added_at: string | null;
}

export const fetchLibrary = () => get<LibraryEntry[]>("/api/library");

export async function removeLibraryPaper(filename: string) {
  const res = await fetch(`/api/library/${encodeURIComponent(filename)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? "Could not remove the paper");
  return data as { title: string; chunks_removed: number; message: string };
}
