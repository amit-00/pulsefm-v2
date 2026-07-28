export type NextStatus = "generating" | "ready" | "fallback";

export interface CurrentSong {
  songId: string;
  title: string;
  artist: string;
  descriptor: string;
  url: string;
  startAt: string;
  endAt: string;
  durationMs: number;
}

export interface NextUp {
  songId: string | null;
  status: NextStatus;
}

export interface StateSnapshot {
  serverTime: string;
  current: CurrentSong;
  next: NextUp;
}
