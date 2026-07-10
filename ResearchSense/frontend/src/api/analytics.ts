import { get } from "./client";

export interface YearRow {
  year: number;
  [campus: string]: number;
}

export interface CitationRow {
  year: number;
  citations: number;
}

export interface VenueRow {
  venue: string;
  publications: number;
}

export interface CampusTotals {
  campus: string;
  researchers: number;
  publications: number;
  citations: number;
}

export interface CrossCampusPair {
  from: string;
  to: string;
  papers: number;
}

export interface AnalyticsOverview {
  campuses: string[];
  publications_per_year: YearRow[];
  citations_per_year: CitationRow[];
  top_venues: VenueRow[];
  campus_totals: CampusTotals[];
  cross_campus_pairs: CrossCampusPair[];
}

export const fetchAnalytics = () => get<AnalyticsOverview>("/api/analytics");
