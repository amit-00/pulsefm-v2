// Task 17, check 4: at a song boundary (forced via POST /tick), the title
// changes and audio swaps.
//
// Run in a tab that was already open and playing, using the
// __pulsefmAudios Set a prior check2-mid-track-start.js run installed in
// that same tab (the patch on HTMLMediaElement.prototype.play stays live
// for the page's lifetime, so it also captures the *next* element the app
// calls .play() on — the incoming track after the swap).
//
// Sequence:
//   1. Have the tab open and playing (check2-mid-track-start.js already run
//      in it).
//   2. From a terminal: read the current version from GET /v1/state, then
//      curl -X POST http://127.0.0.1:8001/tick -H 'Content-Type: application/json' \
//        -d '{"version": N}'   # N = current version + 1
//   3. Wait for the client's next poll (useStation polls every ~2s, plus
//      jitter) to pick up the new snapshot.
//   4. Run this snippet in the tab.

(() => {
  const audios = Array.from(window.__pulsefmAudios || []);
  return audios.map((a) => ({ src: a.src, currentTime: a.currentTime, paused: a.paused }));
})();
