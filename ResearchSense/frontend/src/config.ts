// Product configuration. ResearchSense is a product any organisation can run
// on its own records. Whose research is shown (the name, the kind of
// organisation, its vocabulary and document types) comes from the API, see
// hooks/useOrganisation.ts, so one build serves every deployment.

export const PRODUCT_NAME = "ResearchSense";

/** Wordmark subtitle: kept as a stable product line; the organisation's name
 *  is shown in the hero, footer, and profiles rather than in the wordmark. */
export const BRAND_TAGLINE = "Research Portal";


/** "Campus" -> "Campuses", "Site" -> "Sites". */
export function plural(word: string): string {
  return /(s|x|ch|sh)$/i.test(word) ? `${word}es` : `${word}s`;
}

/** "1 publication", "2 publications": the plural ending for a count. */
export const pluralS = (n: number) => (n === 1 ? "" : "s");
