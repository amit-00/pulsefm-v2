# PulseFM v2

AI-generated lofi radio. Listeners vote on the vibe of the next track; the
winner is generated and plays when the current track ends.

## Status

Slices 0 and 1 are complete: the station rotates through a seeded pool on a
server-driven clock, and the React player joins mid-song in sync. Polls,
voting, auth, and generation land in slices 2 and 3.

## Layout

- `services/radio-service` — rotation clock, sole writer of station state
- `services/station-api` — public read API
- `packages/pulsefm-models` — shared wire models
- `client` — React SPA on Firebase Hosting
- `terraform` — all infrastructure
- `scripts/seed_tracks.py` — seed the fallback pool
- `docs/superpowers/specs` — design documents
- `docs/adr` — architecture decision records

## Development

```bash
uv sync --all-packages
uv run pytest packages/ services/ -m "not integration"

npx -y firebase-tools emulators:exec --only firestore --project pulsefm-test \
  "uv run pytest packages/ services/ -m integration"

cd client && npm install && npm test && npm run dev
```

## Starting a station from empty

```bash
cd terraform && terraform apply
uv run python -m scripts.seed_tracks --bucket "$(terraform output -raw songs_bucket_name)" --dir ./seed-audio
curl -X POST -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "$(terraform output -raw radio_service_url)/bootstrap"
```

After `/bootstrap`, the station is self-driving: each rotation schedules the
next one via Cloud Tasks.
