# 0002. Serve Audio Straight From the Bucket, No CDN

Date: 2026-08-01
Status: Accepted

Supersedes the delivery half of spec decision D1 (discrete tracks over a public
CDN). The rest of D1 — discrete tracks, public bucket, no signed URLs — stands.

## Context

Slice 1 put Cloud CDN in front of the audio bucket: a backend bucket, URL map,
target HTTP proxy, global forwarding rule, and a reserved global address. The
reasoning was cheap shared caching at song boundaries, when every listener
requests the same object at once.

Standing this up revealed three problems, none of which are about caching.

**The client could not be deployed.** The forwarding rule terminated HTTP only —
`audio_base_url` was literally `http://<bare-ip>`, with no certificate and no
domain. Firebase Hosting serves the SPA over HTTPS, and a browser blocks an
`http://` media load from an HTTPS page as mixed content. Slice 1 therefore
shipped a client that could only be run locally, and the README said so.

**The riskiest unknown in the stack lived here.** It is not documented whether
bucket-level CORS is honoured for requests served through a `backend_bucket`,
as opposed to direct `storage.googleapis.com` access. Because
`useAudioSlots` sets `crossOrigin="anonymous"`, a missing
`Access-Control-Allow-Origin` does not degrade anything gracefully — it fails
the load outright and nothing plays. A second, independent hazard: Cloud CDN
does not vary its cache on `Origin` by default, so a response cached for one
origin can be served to another carrying the wrong header.

**It was the largest fixed cost in the stack.** A global external load balancer
bills an hourly forwarding-rule charge (~$18/month) whether or not anyone is
listening. Cloud Run and Firestore are effectively free at this volume.

Meanwhile the caching benefit is close to theoretical at current scale: the
station has no listeners, and browser caching already covers the repeat-listener
case because the uploader stamps every object
`Cache-Control: public, max-age=31536000, immutable`.

## Decision

Delete the CDN. Serve audio directly from
`https://storage.googleapis.com/<bucket>/<object>`.

- `google_compute_backend_bucket`, `google_compute_url_map`,
  `google_compute_target_http_proxy`, `google_compute_global_forwarding_rule`,
  and `google_compute_global_address` are removed from `terraform/storage.tf`.
- The Terraform output `cdn_base_url` becomes `audio_base_url`, and the
  `station-api` environment variable `CDN_BASE_URL` becomes `AUDIO_BASE_URL`.
  Nothing is deployed yet, so renaming is free now and would be a coordinated
  config migration later. A variable named for infrastructure that no longer
  exists is how documentation starts lying.
- The bucket, its `allUsers` public-read binding, and its CORS configuration are
  unchanged.

## Consequences

**HTTPS comes for free**, so the mixed-content blocker is gone and the client
becomes deployable. This was not the motivation for the change but is its most
valuable effect.

**Bucket CORS now applies on the documented path**, removing the failure mode
where the whole `cors` block could have been inert for the URL the player
actually uses.

**No edge caching.** Every fetch reaches the bucket's region. Distant listeners
see worse time-to-first-byte and slower range-seeks when joining mid-track, and
egress scales linearly with listeners instead of being absorbed by a shared
cache. Browser caching is unaffected.

**A custom audio domain on HTTPS is off the table** until a load balancer
returns. GCS supports a CNAME for a custom domain, but HTTP only.

**This is reversible.** Nothing outside `terraform/storage.tf`, `outputs.tf`,
and the `AUDIO_BASE_URL` value depends on how audio is served. `station-api`
composes `{base}/{objectPath}` and does not care what serves it.

## When to put a CDN back

Reach for it when one of these is true — not on principle, and not because the
architecture "should" have one.

**Sustained listening in the thousands of hours per month.** Rates below were
checked against Google Cloud's published pricing on 2026-08-01; re-check them
before acting, because they drift.

| Item | Rate |
|---|---|
| GCS internet egress (Premium Tier, first 1 TB) | $0.12/GB |
| GCS Always Free egress from North America | first 100 GB/month |
| Cloud CDN cache egress (North America, first 10 TiB) | $0.08/GiB (≈ $0.0745/GB) |
| Cloud CDN cache fill (same region) | $0.01/GiB |
| Cloud CDN cache lookup | $0.0075 per 10,000 requests |
| Global forwarding rule (first 5) | $0.025/hour ≈ $18.25/month |

The Always Free 100 GB applies to Cloud Storage egress. Cache egress is a
separate Cloud CDN SKU and does not draw on it, so the no-CDN path is free
where the CDN path is not. Setting the two equal:

```
0.12 × (G − 100)  =  18.25 + 0.0745 × G
              G   ≈  700 GB/month
```

At a ~3.5 MB track (3.5 min, 128 kbps) and ~17 tracks per listener-hour — about
58 MB per listener-hour — that is roughly **12,000 listener-hours per month**,
or **15–20 listeners connected continuously**. Cache fill and lookup charges are
rounding errors here: a radio station fetches each track from origin once and
serves it to everyone.

Note this is listener-*hours*, not concurrency. Twenty people around the clock
and five hundred people for an hour a day cost the same.

**Listeners far from the bucket region.** Egress cost is not the only axis. If
the audience is geographically spread, edge presence improves join latency and
seek responsiveness in a way that no amount of origin capacity will. This can
justify a CDN at any volume, including one listener.

**A custom audio domain on HTTPS.** `audio.pulsefm.app` needs the load balancer
and a managed certificate. This is the most likely trigger in practice.

**Origin egress showing up in the bill.** The observational version of the
first trigger, and the more trustworthy one — it needs no assumptions about
bitrate or listening patterns. Filter the billing console by SKU and watch
Cloud Storage egress (*"Download Worldwide Destinations"*). When it approaches
~$18/month, the CDN has started paying for itself.

Restoring it means re-adding the five resources, pointing `audio_base_url` at
the new address, and — importantly — **adding the HTTPS proxy and managed
certificate that the original never had**, since re-adding an HTTP-only
forwarding rule would reintroduce the mixed-content blocker this ADR removed.
Re-verify bucket CORS through the `backend_bucket` path at that point, and set a
cache key policy that varies on `Origin`.
