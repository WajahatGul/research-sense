import { get } from "./client";

export type SuggestScope = "researchers" | "topics" | "publications";

export interface Suggestion {
  kind: "researcher" | "topic" | "publication";
  id: number;
  label: string;
  detail: string;
}

export const fetchSuggestions = (q: string, scope?: SuggestScope, limit = 5) =>
  get<Suggestion[]>("/api/suggest", { q, scope, limit });
