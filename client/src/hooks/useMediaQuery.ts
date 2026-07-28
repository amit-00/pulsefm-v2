import { useEffect, useState } from "react";

/**
 * jsdom (and, in principle, any non-browser renderer) has no matchMedia.
 * Default to false rather than crash or force a particular breakpoint on
 * environments that can't answer either way.
 */
function matchesQuery(query: string): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(query).matches;
}

/**
 * Tracks a CSS media query live via a change listener, following the same
 * pattern Waveform's useReducedMotion establishes: initialise from
 * matchMedia, then listen so a resize mid-session is honoured on its own
 * rather than only on the next unrelated render.
 */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => matchesQuery(query));

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mediaQueryList = window.matchMedia(query);
    setMatches(mediaQueryList.matches);
    const onChange = (event: MediaQueryListEvent) => setMatches(event.matches);

    // Modern browsers expose EventTarget's addEventListener/removeEventListener
    // on MediaQueryList. Safari < 14 only has the deprecated
    // addListener/removeListener pair; both are typed on MediaQueryList in
    // lib.dom, so no assertion is needed to call either.
    if (typeof mediaQueryList.addEventListener === "function") {
      mediaQueryList.addEventListener("change", onChange);
      return () => mediaQueryList.removeEventListener("change", onChange);
    }

    mediaQueryList.addListener(onChange);
    return () => mediaQueryList.removeListener(onChange);
  }, [query]);

  return matches;
}
