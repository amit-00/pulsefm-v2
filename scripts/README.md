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
