import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/client";

/** Retry only what a second attempt can fix.
 *
 * A dropped connection (status 0), a timeout (504) or a server error (5xx)
 * may succeed next time. A 4xx — a missing profile, a bad filter, a refused
 * sign-in — will fail identically, so retrying only doubles the load and
 * keeps the visitor waiting a second longer for the real answer.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return false;
  }
  return true;
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: shouldRetry,
      refetchOnWindowFocus: false,
    },
  },
});
