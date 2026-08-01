// Product configuration. ResearchSense is institution-agnostic: it ships as a
// product any university can deploy, branded from this one place. A deployment
// is always for a specific university (the customer), so the institution name
// is set here; this build is configured for Bahria University, which owns the
// data and the campuses shown in the app. A different customer overrides it at
// build time via VITE_INSTITUTION_NAME (or clears it to "" for a neutral look).

export const PRODUCT_NAME = "ResearchSense";

export const INSTITUTION_NAME: string =
  (import.meta.env.VITE_INSTITUTION_NAME ?? "Bahria University").trim();

/** Wordmark subtitle: kept as a stable product line; the institution name is
 *  shown in the hero, footer, and profiles rather than in the wordmark. */
export const BRAND_TAGLINE = "Research Portal";

/** "<the institution>" phrase for prose, e.g. "researchers at Meridian
 *  University" vs a neutral "researchers across the platform". */
export const INSTITUTION_OF = INSTITUTION_NAME
  ? `at ${INSTITUTION_NAME}`
  : "across the institution";
