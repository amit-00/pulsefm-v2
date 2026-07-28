import type { StateSnapshot } from "./types";

export class StationUnavailableError extends Error {
  constructor(status: number) {
    super(`Station API returned ${status}. The station may not have started yet.`);
    this.name = "StationUnavailableError";
  }
}

export async function fetchState(baseUrl: string, signal?: AbortSignal): Promise<StateSnapshot> {
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/state`, { signal });
  if (!response.ok) {
    throw new StationUnavailableError(response.status);
  }
  return (await response.json()) as StateSnapshot;
}
