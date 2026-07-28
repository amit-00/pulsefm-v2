/**
 * Server-clock correction.
 *
 * Every listener seeks to (serverNow - startAt), so a skewed device clock would
 * put that listener out of sync with the station. Background tabs also throttle
 * timers, so local elapsed time drifts; correcting against the server's own
 * timestamp on every poll keeps the audio and the UI honest.
 */

export function computeOffsetMs(serverTimeIso: string, receivedAtMs: number): number {
  return Date.parse(serverTimeIso) - receivedAtMs;
}

export function serverNow(offsetMs: number, nowMs: number = Date.now()): number {
  return nowMs + offsetMs;
}

export function positionMs(
  startAtIso: string,
  offsetMs: number,
  nowMs: number = Date.now(),
): number {
  return Math.max(0, serverNow(offsetMs, nowMs) - Date.parse(startAtIso));
}
