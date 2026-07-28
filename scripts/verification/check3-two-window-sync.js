// Task 17, check 3: a second browser context shows the same position within
// roughly a second.
//
// Run `press-and-read.js` (below) in a *second* tab/window at the same URL
// while the first tab is already open and playing. Then run
// `read-live-position.js` in the first tab immediately after, to read its
// live position back for comparison. See README.md for the normalization
// math used to compare the two readings (taken at slightly different wall
// clock instants).

// --- press-and-read.js: run in the new tab ---
(async () => {
  window.__pulsefmAudios = new Set();
  const origPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function (...args) {
    window.__pulsefmAudios.add(this);
    return origPlay.apply(this, args);
  };
  const button = document.querySelector('button[aria-label="Play"]');
  if (!button) return { error: "no Play button" };
  button.click();
  await new Promise((r) => setTimeout(r, 400));
  const audios = Array.from(window.__pulsefmAudios);
  return {
    readIso: new Date().toISOString(),
    audioInfo: audios.map((a) => ({ src: a.src, currentTime: a.currentTime, paused: a.paused })),
  };
})();

// --- read-live-position.js: run immediately after, in the tab that was
// already playing (reuses the __pulsefmAudios Set that tab's own earlier
// check-2 run installed) ---
(() => {
  const audios = Array.from(window.__pulsefmAudios || []);
  return {
    readIso: new Date().toISOString(),
    audioInfo: audios.map((a) => ({ src: a.src, currentTime: a.currentTime, paused: a.paused })),
  };
})();
