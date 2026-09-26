import { describe, expect, it } from "vitest";

import { ApiError } from "../api/client";
import { shouldRetry } from "./queryClient";

describe("shouldRetry", () => {
  it("does not retry a request that can only fail the same way", () => {
    expect(shouldRetry(0, new ApiError(404, "Researcher not found"))).toBe(false);
    expect(shouldRetry(0, new ApiError(422, "bad filter"))).toBe(false);
  });

  it("retries once for transient failures", () => {
    expect(shouldRetry(0, new ApiError(0, "offline"))).toBe(true);
    expect(shouldRetry(0, new ApiError(504, "timed out"))).toBe(true);
    expect(shouldRetry(0, new ApiError(503, "down"))).toBe(true);
    expect(shouldRetry(0, new Error("unexpected"))).toBe(true);
  });

  it("gives up after one retry", () => {
    expect(shouldRetry(1, new ApiError(503, "down"))).toBe(false);
  });
});
