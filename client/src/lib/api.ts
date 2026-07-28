import type { StateSnapshot } from "./types";

export class StationUnavailableError extends Error {
  /** Kept as a field, not just interpolated: callers branch on 503 ("the
   *  station has not started yet") versus everything else. */
  readonly status: number;

  constructor(status: number) {
    super(
      status === 503
        ? "The station has not started yet."
        : `Station API returned ${status}.`,
    );
    this.name = "StationUnavailableError";
    this.status = status;
  }
}

export async function fetchState(baseUrl: string, signal?: AbortSignal): Promise<StateSnapshot> {
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/state`, { signal });
  if (!response.ok) {
    throw new StationUnavailableError(response.status);
  }
  return (await response.json()) as StateSnapshot;
}
