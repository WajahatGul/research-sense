import { get } from "./client";
import type { Paginated, Publication } from "../types";

export interface PublicationFilters {
  q?: string;
  year?: number;
  topic_id?: number;
  author_id?: number;
  campus?: string;
  year_from?: number;
  year_to?: number;
  date_from?: string;
  date_to?: string;
  department?: string;
  publication_type?: string;
  page?: number;
  page_size?: number;
}

export const fetchPublications = (filters: PublicationFilters = {}) =>
  get<Paginated<Publication>>("/api/publications", filters);

export const fetchPublicationYears = () =>
  get<number[]>("/api/publications/years");

export const fetchPublication = (id: number) =>
  get<Publication>(`/api/publications/${id}`);

export const fetchRelatedPublications = (id: number, limit = 5) =>
  get<Publication[]>(`/api/publications/${id}/related`, { limit });
