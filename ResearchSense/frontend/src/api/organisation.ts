import { get } from "./client";

export interface DocumentType {
  key: string;
  label: string;
  count: number;
}

/** Who this deployment serves and the words it uses (see the backend's
 * app/core/organisation.py). */
export interface Organisation {
  name: string; // "" when the deployment is unbranded
  kind: string;
  noun: string; // "institution", "company", "organisation", "agency"
  people: string;
  unit: string;
  site: string;
  document_types: DocumentType[];
}

export const fetchOrganisation = () => get<Organisation>("/api/organisation");
