import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

/** On a new page: scroll to the top and put focus at the start of the content.
 *
 * A client-side navigation does not reload the page, so without this the
 * keyboard focus stayed on the link just clicked (often in the header) and
 * a screen reader announced nothing: the new page arrived in silence.
 * Focus moves only when the path actually changed, so the initial load
 * (which React may run twice in development) starts at the top of the
 * document as usual, where "Skip to content" is the first Tab stop.
 */
export function useScrollTop() {
  const { pathname } = useLocation();
  const shown = useRef(pathname);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
    if (shown.current === pathname) return;
    shown.current = pathname;
    document.getElementById("main")?.focus({ preventScroll: true });
  }, [pathname]);
}
