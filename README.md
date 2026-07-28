# PulseFM v2

AI-generated lofi radio. Listeners vote on the vibe of the next track; the
winner is generated and plays when the current track ends.

## Status

Slices 0 and 1 are complete: the station rotates through a seeded pool on a
server-driven clock, and the React player joins mid-song in sync. Polls,
voting, auth, and generation land in slices 2 and 3.

Nothing below has been run against real infrastructure. The Terraform is
`validate`-clean but has never been applied, and no GCP project exists yet.

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

This is a three-stage `terraform apply`, not one. `cloud_run.tf` references
`:latest` images in an Artifact Registry repository that the same apply
would otherwise be creating — a single `terraform apply` from empty fails
trying to deploy Cloud Run services against images that don't exist yet.
The registry and the project APIs have to exist *before* an image can be
pushed, and `radio-service`'s own URL has to exist *before* `tick_url` (its
self-referencing successor-scheduling target) can be set — hence three
passes.

Set these once, matching your `terraform.tfvars`:

```bash
PROJECT_ID="pulsefm-v2"     # terraform.tfvars: project_id
REGION="us-central1"        # terraform.tfvars: region
```

**Stage 1 — create the registry and enabled APIs only** (nothing else has
anything to reference yet):

```bash
cd terraform
terraform apply \
  -target=google_project_service.enabled \
  -target=google_artifact_registry_repository.services
```

**Stage 2 — build and push both images** (commands lifted from the plan,
Task 11 Step 5; run from the repo root, since the Dockerfiles' build context
is the whole repo):

```bash
cd ..
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/pulsefm"
gcloud auth configure-docker "${REGION}-docker.pkg.dev"
docker build -f services/radio-service/Dockerfile -t "${IMAGE_BASE}/radio-service:latest" .
docker build -f services/station-api/Dockerfile -t "${IMAGE_BASE}/station-api:latest" .
docker push "${IMAGE_BASE}/radio-service:latest"
docker push "${IMAGE_BASE}/station-api:latest"
```

**Stage 3 — full apply**, which now finds images to deploy:

```bash
cd terraform
terraform apply
```

`radio_service_url` is only known after this apply (Cloud Run assigns it).
`tick_url` is still empty at this point — the service is up, but nothing
will chain rotations yet — so read the URL, set it, and apply once more:

```bash
echo "tick_url = \"$(terraform output -raw radio_service_url)/tick\"" >> terraform.tfvars
terraform apply
cd ..
```

**Seed the fallback pool:**

```bash
uv run python -m scripts.seed_tracks \
  --bucket "$(terraform -chdir=terraform output -raw songs_bucket_name)" \
  --dir ./seed-audio
```

**Bootstrap the station.** `radio-service` has `ingress =
INGRESS_TRAFFIC_INTERNAL_ONLY` (`terraform/cloud_run.tf`) — deliberately;
this is not being changed. A `curl` from a laptop is rejected at the
network layer before IAM is even consulted, so the obvious
`curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" .../bootstrap`
does not work, no matter what identity you authenticate as.
`terraform/iam.tf` also only grants `roles/run.invoker` to the
`pulsefm-tick-invoker` service account, not to any human — so even from
inside the network, your own user has no invoke permission.

The one path that already reaches this service is the one it's built
around: Cloud Tasks, same project, calling as `pulsefm-tick-invoker`. That
route is same-project internal traffic (see the comment on
`google_cloud_run_v2_service.radio` in `terraform/cloud_run.tf`) and is
exactly how every subsequent `/tick` call already works — so a one-shot
Cloud Task calling `/bootstrap` the same way is the production-faithful
option, not a workaround: it reuses infrastructure that's already proven
to work rather than adding a new access path. It requires one IAM grant
this repo does not create by design (bootstrap is a one-time operator
action, not a standing permission):

```bash
gcloud iam service-accounts add-iam-policy-binding \
  "pulsefm-tick-invoker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/iam.serviceAccountUser"

gcloud tasks create-http-task \
  --queue=radio-queue \
  --location="${REGION}" \
  --url="$(terraform -chdir=terraform output -raw radio_service_url)/bootstrap" \
  --oidc-service-account-email="pulsefm-tick-invoker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --oidc-token-audience="$(terraform -chdir=terraform output -raw radio_service_url)"
```

You also need `roles/cloudtasks.enqueuer` (or an equivalent custom role) on
the project for your own user, to create the task in the first place.

(An alternative worth knowing about: `gcloud run services proxy` is
commonly suggested for reaching IAM-protected Cloud Run services from a
laptop, but it does **not** bypass `INGRESS_TRAFFIC_INTERNAL_ONLY` — it
still has to reach the service over the network, and an internal-only
service is unreachable from outside its VPC regardless of IAM. It was
considered and rejected for this step for that reason.)

After `/bootstrap` succeeds, the station is self-driving: each rotation
schedules the next one via Cloud Tasks, using the exact same OIDC path
just exercised by hand.

## Deploying the client

The client is **not deployable yet**, independent of the backend steps
above. Firebase Hosting serves HTTPS only; the CDN in front of the audio
bucket (`terraform/storage.tf`) currently has only an HTTP target proxy
(`google_compute_target_http_proxy`), with no certificate or HTTPS
forwarding rule. A browser loading the SPA over HTTPS and pointed at an
`http://` audio URL blocks the load as mixed content. Slice 4 is where TLS
in front of the CDN is planned to land; until then, `npm run dev` against a
deployed backend is the only way to hear the station end to end.
