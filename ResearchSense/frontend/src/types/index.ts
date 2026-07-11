// TypeScript contracts mirroring the FastAPI Pydantic schemas.

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Stats {
  researchers: number;
  publications: number;
  projects: number;
  topics: number;
  departments: number;
  campuses: number;
}

export interface TopicRef {
  topic_id: number;
  topic_name: string;
}

export interface Topic {
  topic_id: number;
  topic_name: string;
  description: string;
  icon: string;
  publication_count: number;
  researcher_count: number;
  source: string;
}

export interface AuthorRef {
  researcher_id: number | null;
  full_name: string;
  order: number;
}

export interface Publication {
  publication_id: number;
  title: string;
  abstract: string;
  doi: string | null;
  publication_year: number;
  journal_name: string;
  publication_type: string;
  citation_count: number;
  campus: string;
  authors: AuthorRef[];
  topics: TopicRef[];
  source: string;
}

export interface PublicationRef {
  publication_id: number;
  title: string;
  publication_year: number;
  journal_name: string;
  citation_count: number;
  doi: string | null;
}

export interface Researcher {
  researcher_id: number;
  full_name: string;
  designation: string;
  department: string;
  campus: string;
  institution: string;
  email: string | null;
  orcid_id: string | null;
  photo_url: string | null;
  expertise: string;
  publication_count: number;
  citation_count: number;
  topics: TopicRef[];
  source: string;
}

export interface CollaborationSuggestion {
  researcher_id: number;
  full_name: string;
  designation: string;
  department: string;
  similarity_score: number;
  basis: string;
}

export interface ResearcherDetail extends Researcher {
  profile_bio: string;
  education: string;
  google_scholar_id: string | null;
  scopus_id: string | null;
  publications: PublicationRef[];
  collaborators: CollaborationSuggestion[];
}

export interface Funding {
  funding_id: number;
  agency_name: string;
  country: string;
  amount: number;
  currency: string;
}

export interface Project {
  project_id: number;
  project_title: string;
  description: string;
  start_date: string;
  end_date: string | null;
  status: string;
  principal_investigator_id: number | null;
  principal_investigator_name: string;
  department: string;
  campus: string;
  funding: Funding[];
  topics: string[];
  source: string;
}

export interface ChatSource {
  label: string;
  kind: string;
  ref_id: number | null;
}

export interface ChatResponse {
  answer: string;
  sources: ChatSource[];
}
