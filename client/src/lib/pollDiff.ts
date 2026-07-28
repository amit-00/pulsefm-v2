import type { StateSnapshot } from "./types";

export interface SnapshotDiff {
  songChanged: boolean;
  nextSongChanged: boolean;
}

/**
 * Derive UI transitions by comparing consecutive snapshots.
 *
 * Polling gives us state, not events. Diffing recovers the events the UI needs
 * (swap the audio slot, prefetch the next track) without a push channel.
 */
export function diffSnapshots(
  previous: StateSnapshot | null,
  next: StateSnapshot,
): SnapshotDiff {
  if (previous === null) {
    return { songChanged: true, nextSongChanged: true };
  }
  return {
    songChanged: previous.current.songId !== next.current.songId,
    nextSongChanged: previous.next.songId !== next.next.songId,
  };
}
