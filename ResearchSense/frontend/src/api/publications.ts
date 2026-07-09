import { get } from "./client";
import type { Paginated, Publication } from "../types";

export interface PublicationFilters {
  q?: string;
  year?: number;
  topic_id?: number;
  author_id?: number;
  campus?: string;
  page?: number;
  page_size?: number;
}

export const fetchPublications = (filters: PublicationFilters = {}) =>
  get<Paginated<Publication>>("/api/publications", filters);

export const fetchPublicationYears = () =>
  get<number[]>("/api/publications/years");
