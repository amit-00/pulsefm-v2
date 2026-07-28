# Task 17 browser verification: method and raw readings

This directory holds the exact browser-console JS snippets used to produce
the numbers in the task-17 report for checks 2-4, plus the raw readings
those snippets returned. It exists so the sync numbers can be inspected
rather than taken on faith.

There are no screenshot **files** here. Screenshots were viewed inline
through the browser-automation tool during the session (not written to
disk by that tool), and per the coordinator's instruction this pass did not
re-run the browser checks to go back and capture them — only the check-5
breakpoint change (see below) plausibly needed re-verification, and that one
was re-run and is described in `task-17-report.md`. The JS snippets and
their returned JSON, reproduced verbatim below and in the sibling `.js`
files, are what actually generated the check 2/3/4 numbers.

## How to reproduce

1. Stand up the local system per `task-17-report.md`'s "Local bring-up"
   section (Firestore emulator, `dev_radio_app`, `dev_station_app`,
   `POST /bootstrap`, `npm run dev`).
2. Open the app in a browser, open devtools, paste the contents of
   `check2-mid-track-start.js` into the console, and read the result.
3. For check 3, open a second tab/window at the same URL and run the same
   snippet there, then re-run `check3-two-window-sync-readback.js` in the
   first tab to read its live position back.
4. For check 4, force a rotation with
   `curl -X POST http://127.0.0.1:8001/tick -H 'Content-Type: application/json' -d '{"version": N}'`
   (N = current version + 1, readable from `GET /v1/state`), then run
   `check4-boundary-swap.js` in a tab that was already open and playing
   before the tick.

All three snippets rely on the same technique: `useAudioSlots` creates its
`<audio>` elements with `new Audio()` and never attaches them to the
document, so `document.querySelectorAll('audio')` finds nothing. Each
snippet installs a one-line monkey-patch on
`HTMLMediaElement.prototype.play` from the browser console — not from any
committed source file — to capture a reference to whichever element the
app itself calls `.play()` on. This is a client-side-only technique, is
never loaded by the app, and does not touch `useAudioSlots.ts` or any other
existing hook.

## Note on track length

The brief specified 20-30s fixtures. In this environment, each
browser-automation round trip (screenshot, JS eval, click) cost on the
order of tens of seconds of real wall-clock time — a handful of them in
sequence exceeded a 20-30s track's runtime before the check could even be
read. `scripts/dev_fixtures.py` was changed to 720-900s tracks so the
multi-step checks (read position, open a second window, compare, force a
tick) had enough runway to complete against a track that was still playing.

This was a reasonable adaptation to automation latency, not a change to the
thing being tested, but it does mean **the sync numbers below were measured
against files 30-45x longer than a production track** (~230s in the
brief's own `Player.test.tsx` fixture data). WAV range-request seek cost
can scale with file size (more index/scan work for the browser and the
static file server to locate a byte offset in a larger file), so a
production-sized file could show different — plausibly better, since
there's less file to seek through — timing than what's recorded here. The
numbers should be read as "the mechanism works and is sub-second," not as
a precise bound that will hold unchanged at production track lengths.

## Raw readings

### Check 2 — mid-track start (single tab, fresh 900s track)

```json
{
  "beforeClickIso": "2026-07-28T20:18:28.660Z",
  "readIso": "2026-07-28T20:18:29.094Z",
  "state": {
    "current": {
      "songId": "tone-a",
      "startAt": "2026-07-28T20:18:12Z",
      "durationMs": 900000
    },
    "serverTime": "2026-07-28T20:18:29Z"
  },
  "audioInfo": [
    {
      "src": "http://localhost:5173/tracks/tone-a.wav",
      "currentTime": 16.297696,
      "paused": false,
      "duration": 900,
      "readyState": 4
    }
  ],
  "expectedPositionS": 17.094
}
```

Analysis: `expectedPositionS` is `(readIso − startAt) / 1000`, i.e. where
the station's server clock says playback should be at the instant the
reading was taken. The actual `audio.currentTime` (16.298s) sits 0.796s
behind that — within the brief's "roughly a second" tolerance, and
consistent with real playback start-up latency (buffering/decode before
`currentTime` begins advancing), not with starting from 0:00.

### Check 3 — two windows agree

Tab B (second window), read first:

```json
{
  "readIso": "2026-07-28T20:19:01.382Z",
  "audioInfo": [
    { "src": "http://localhost:5173/tracks/tone-a.wav", "currentTime": 48.562147, "paused": false }
  ]
}
```

Tab A (already open and playing), read ~6.3s later:

```json
{
  "readIso": "2026-07-28T20:19:07.661Z",
  "audioInfo": [
    { "src": "http://localhost:5173/tracks/tone-a.wav", "currentTime": 54.875401, "paused": false }
  ]
}
```

Analysis: normalizing Tab A's reading back to Tab B's read instant
(`54.875401 − (20:19:07.661 − 20:19:01.382)` = `54.875401 − 6.279` =
`48.596401`) and comparing to Tab B's actual reading of `48.562147` gives a
difference of **0.034s** between the two browser contexts.

### Check 4 — boundary swap (forced via POST /tick)

Server side, before/after the tick:

```json
// before: GET /v1/state
{"current": {"songId": "tone-a", ...}, ...}

// POST /tick {"version": 2}
{"status": "rotated", "songId": "tone-b", "version": 2}

// after: GET /v1/state
{"current": {"songId": "tone-b", "startAt": "2026-07-28T20:19:22Z", "durationMs": 720000, ...}, ...}
```

Client side, read from the tab that was already open and playing `tone-a`
before the tick (after its next poll picked up the new snapshot):

```json
[
  { "src": "http://localhost:5173/tracks/tone-a.wav", "currentTime": 70.525026, "paused": true },
  { "src": "http://localhost:5173/tracks/tone-b.wav", "currentTime": 11.805556, "paused": false }
]
```

Analysis: two distinct `<audio>` elements are visible — the original
`tone-a.wav` element, now paused; and a second element with `tone-b.wav`
as its src, actively playing. This is the dual-slot swap `useAudioSlots`
implements (see its updated comment): the outgoing element was paused
while a different, idle element was assigned the incoming src and started,
rather than the same element being re-sourced in place.
