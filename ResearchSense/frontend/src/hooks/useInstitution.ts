import { useOrganisation } from "./useOrganisation";

/** The organisation's name for use in a sentence: its own name when one is
 * configured, otherwise "this institution" / "this company", so prose such
 * as "If you research at …" still reads correctly on an unbranded deployment.
 */
export function useInstitution(): string {
  const org = useOrganisation();
  return org.name || `this ${org.noun}`;
}
