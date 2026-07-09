import { useEffect } from "react";
import { useLocation } from "react-router-dom";

// Scrolls to the top of the page whenever the route path changes.
export function useScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname]);
}
