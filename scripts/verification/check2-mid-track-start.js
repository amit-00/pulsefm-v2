// Task 17, check 2: pressing play starts audio mid-track, at the station's
// position — not at 00:00.
//
// Paste into the browser devtools console on the running client, after
// POST /bootstrap and before pressing Play, then read the returned object.
// See README.md in this directory for how "expectedPositionS" is used.
//
// useAudioSlots creates its <audio> elements with `new Audio()` and never
// attaches them to the document, so document.querySelectorAll('audio')
// finds nothing — this monkey-patches HTMLMediaElement.prototype.play from
// the console (not from any committed source) to capture whichever element
// the app itself calls .play() on.

(async () => {
  window.__pulsefmAudios = new Set();
  const origPlay = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function (...args) {
    window.__pulsefmAudios.add(this);
    return origPlay.apply(this, args);
  };

  const button = document.querySelector('button[aria-label="Play"]');
  if (!button) {
    return { error: "no Play button found", bodyText: document.body.innerText.slice(0, 300) };
  }

  const beforeClickIso = new Date().toISOString();
  button.click();

  // Give the click handler + effect a moment to run.
  await new Promise((r) => setTimeout(r, 400));

  const res = await fetch("http://localhost:8000/v1/state");
  const state = await res.json();
  const readIso = new Date().toISOString();

  const audios = Array.from(window.__pulsefmAudios);
  const audioInfo = audios.map((a) => ({
    src: a.src,
    currentTime: a.currentTime,
    paused: a.paused,
    duration: a.duration,
    readyState: a.readyState,
  }));

  const expectedPositionS = (Date.parse(readIso) - Date.parse(state.current.startAt)) / 1000;

  return { beforeClickIso, readIso, state, audioInfo, expectedPositionS };
})();
