// Product configuration. ResearchSense is institution-agnostic: it ships as a
// product any university can deploy. Set INSTITUTION_NAME to brand the app for
// one institution; leave it empty for the neutral product-only look.
//
// This is the single place to set the institution name on the client. It can
// also be provided at build time via VITE_INSTITUTION_NAME.

export const PRODUCT_NAME = "ResearchSense";

export const INSTITUTION_NAME: string =
  (import.meta.env.VITE_INSTITUTION_NAME ?? "").trim();

/** Wordmark subtitle: the institution when set, else a neutral product line. */
export const BRAND_TAGLINE = INSTITUTION_NAME || "Research Portal";

/** "<the institution>" phrase for prose, e.g. "researchers at Meridian
 *  University" vs a neutral "researchers across the platform". */
export const INSTITUTION_OF = INSTITUTION_NAME
  ? `at ${INSTITUTION_NAME}`
  : "across the institution";
