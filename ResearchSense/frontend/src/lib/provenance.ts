/** Where a publication record came from, in words a reader can weigh.
 *
 * Harvested papers are linked to faculty by matching author names, which can
 * credit a paper to a namesake; papers an author submitted were confirmed by
 * that author and approved. Saying which is which lets a reader judge the
 * link between paper and person instead of assuming it.
 */
export function provenance(source: string | undefined): {
  label: string;
  detail: string;
} {
  if (source === "doi" || source === "manual") {
    return {
      label: "Added by the author",
      detail: "Submitted by the researcher through the faculty portal and approved.",
    };
  }
  if (source?.startsWith("openalex")) {
    return {
      label: "via OpenAlex",
      detail:
        "Harvested from OpenAlex and linked to faculty by author-name matching; a namesake may occasionally be credited.",
    };
  }
  return { label: "Sample record", detail: "Illustrative data, not a verified publication." };
}
