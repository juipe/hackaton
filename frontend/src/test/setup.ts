import "@testing-library/jest-dom/vitest";

import { afterEach, beforeEach, vi } from "vitest";

/**
 * A fixed, deliberately non-UTC zone. Pinning it makes date assertions
 * reproducible on any machine, and picking a zone behind Greenwich means the
 * midday-UTC anchoring in `dateInputToIso` is actually exercised: a midnight-UTC
 * anchor would render as the previous day here, and the tests would catch it.
 */
process.env.TZ = "America/Los_Angeles";

type Mutable = Record<string, unknown>;
const globals = globalThis as unknown as Mutable;

/* jsdom implements neither of these, and Radix/Recharts construct them eagerly. */
if (!globals.ResizeObserver) {
  globals.ResizeObserver = class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
}

if (!globals.IntersectionObserver) {
  globals.IntersectionObserver = class {
    readonly root = null;
    readonly rootMargin = "";
    readonly thresholds: number[] = [];
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
    takeRecords(): [] {
      return [];
    }
  };
}

if (typeof window !== "undefined" && !window.matchMedia) {
  window.matchMedia = (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

/* Radix menus and selects call these during open/close; jsdom leaves them out. */
if (typeof Element !== "undefined") {
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = () => {};
  }
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
}

/**
 * Nothing in the suite is allowed to touch the network. Every test starts with a
 * fetch that answers "not authenticated", so a component mounted without an
 * explicit stub still resolves to a deterministic signed-out state instead of
 * hanging or hitting a real socket. Tests that care override it with vi.stubGlobal.
 */
beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async () =>
        new Response(JSON.stringify({ detail: "Требуется вход" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
    ),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});
