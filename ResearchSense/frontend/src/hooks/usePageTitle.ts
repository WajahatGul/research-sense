import { useEffect } from "react";

const SITE = "ResearchSense";

/** Name the page in the browser tab, history and screen-reader announcement.
 *
 * Every route used to be titled just "ResearchSense", so open tabs, the
 * Back menu and a screen reader arriving on a page could not tell a
 * profile from the analytics (WCAG 2.4.2).
 */
export function usePageTitle(title?: string | null): void {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE}` : SITE;
  }, [title]);
}
