import type { PublicationRef } from "../types";

/**
 * Stably reorders `pubs` so that publications co-authored by BOTH
 * `profileId` (the profile being viewed) and `withId` (the researcher the
 * user arrived from) appear first, preserving the existing relative order
 * within each group. A no-op when `withId` is not given, or when it never
 * co-authored anything with `profileId`.
 */
export function coauthoredFirst(
  pubs: PublicationRef[],
  profileId: number,
  withId: number | null,
): PublicationRef[] {
  if (withId == null) return pubs;

  const shared: PublicationRef[] = [];
  const rest: PublicationRef[] = [];
  for (const p of pubs) {
    const ids = p.author_ids ?? [];
    if (ids.includes(profileId) && ids.includes(withId)) {
      shared.push(p);
    } else {
      rest.push(p);
    }
  }
  return shared.length > 0 ? [...shared, ...rest] : pubs;
}
