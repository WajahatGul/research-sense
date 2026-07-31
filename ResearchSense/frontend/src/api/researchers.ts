import { get } from "./client";
import type {
  CollaborationSuggestion,
  Paginated,
  Researcher,
  ResearcherDetail,
} from "../types";

export interface ResearcherFilters {
  q?: string;
  campus?: string;
  department?: string;
  designation?: string;
  topic_id?: number;
  page?: number;
  page_size?: number;
}

export const fetchResearchers = (filters: ResearcherFilters = {}) =>
  get<Paginated<Researcher>>("/api/researchers", filters);

export const fetchFeaturedResearchers = (limit = 6) =>
  get<Researcher[]>("/api/researchers/featured", { limit });

export const fetchDepartments = () =>
  get<string[]>("/api/researchers/departments");

export const fetchDesignations = () =>
  get<string[]>("/api/researchers/designations");

export const fetchCampuses = () =>
  get<string[]>("/api/researchers/campuses");

export const fetchResearcher = (id: number) =>
  get<ResearcherDetail>(`/api/researchers/${id}`);

export type CollabSort =
  | "relevance" | "shared_areas" | "coauthored" | "name" | "campus";

export const fetchCollaborators = (id: number, sort: CollabSort = "relevance") =>
  get<CollaborationSuggestion[]>(`/api/researchers/${id}/collaborators`, { sort });
