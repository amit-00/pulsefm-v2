# scripts

## seed_tracks.py

Seeds the fallback pool. Slice 1 has no generation, so this is the only source
of songs. Requires `ffprobe` (part of ffmpeg) on PATH.

```bash
uv run python -m scripts.seed_tracks \
  --bucket "$(cd terraform && terraform output -raw songs_bucket_name)" \
  --dir ./seed-audio \
  --project "$PROJECT_ID"
```

Use at least four tracks of differing lengths so rotation and the fallback
ordering are both observable.

## Running the whole station locally

Two commands. The backend runs in Docker; the client runs on the host.

```bash
docker compose up -d          # emulator, both services, seeds, and bootstraps
cd client && npm ci && VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Then open http://localhost:5173. The station is already playing — `docker
compose up` seeds three generated WAV fixtures and calls `/bootstrap` for you.

`docker compose down -v` tears it down, including the emulator's data.

### Why the client is not in compose

Vite's file watcher needs polling over macOS bind mounts or HMR silently stops
working, `npm ci` would re-run on every `up`, and the dev server only ever
talks to `localhost`. Containerising it costs speed and buys nothing.

### Rotation is manual

There is no Cloud Tasks locally, so nothing chains ticks — `scripts/dev_radio_app.py`
injects a no-op scheduler through `build_app`'s existing seam rather than
patching `main.py`. Force a changeover with the *next* version:

```bash
curl -X POST http://127.0.0.1:8001/tick -H 'Content-Type: application/json' -d '{"version": 2}'
```

Read the current version from `GET http://127.0.0.1:8000/v1/state` and add one.
A tick carrying the version already committed is correctly rejected as stale.

### Ports

| Port | What |
|---|---|
| 5173 | client (host) — also serves the audio fixtures at `/tracks/` |
| 8000 | station-api — `/v1/state`, `/v1/queue` |
| 8001 | radio-service — `/tick`, `/bootstrap` |
| 8080 | Firestore emulator |

### Without Docker

The four-terminal equivalent, if you would rather not run containers:

```bash
python3 -m scripts.dev_gen_tones                       # generate WAV fixtures
cd scripts/dev-firebase && npx -y firebase-tools emulators:start --only firestore --project pulsefm-local

export FIRESTORE_EMULATOR_HOST=127.0.0.1:8080
uv run python -m scripts.dev_seed_station
uv run uvicorn scripts.dev_radio_app:app --port 8001   # terminal 2
FIRESTORE_EMULATOR_HOST=127.0.0.1:8080 AUDIO_BASE_URL=http://localhost:5173 \
  uv run uvicorn scripts.dev_station_app:app --port 8000   # terminal 3
curl -X POST http://127.0.0.1:8001/bootstrap
```

Note `python3 -m scripts.dev_gen_tones`, not `python3 scripts/dev_gen_tones.py` —
the latter fails with `ModuleNotFoundError: No module named 'scripts'`.
