import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

/**
 * @testing-library/dom's `waitFor` only drives fake timers when it detects a
 * global `jest` with an active clock; it has no Vitest-specific detection.
 * Without this alias, waitFor's re-check loop never runs under
 * `vi.useFakeTimers()` and hangs until the real test timeout. Vitest's fake
 * clock satisfies the same detection check, so aliasing just the one method
 * testing-library calls is enough to make waitFor pump the fake clock itself.
 */
if (typeof (globalThis as { jest?: unknown }).jest === "undefined") {
  Object.defineProperty(globalThis, "jest", {
    value: { advanceTimersByTime: vi.advanceTimersByTime.bind(vi) },
    writable: true,
    configurable: true,
  });
}
