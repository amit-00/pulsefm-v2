resource "google_storage_bucket" "songs" {
  name          = var.songs_bucket_name
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  # This is a SLICE-1 PLAYBACK BLOCKER, not a slice-4 analyser concern:
  # client/src/hooks/useAudioSlots.ts sets crossOrigin="anonymous" on the
  # <audio> element today, which makes every track fetch a CORS request. A
  # response without Access-Control-Allow-Origin fails the load outright —
  # no audio plays, full stop. (It will *also* matter for the slice 4
  # WebAudio analyser, which needs the same headers or silently reads zeros,
  # but that's secondary to playback working at all.)
  #
  # NOT YET CONFIRMED: it isn't documented whether bucket-level CORS is
  # honoured for requests served through the backend_bucket/Cloud CDN path,
  # as opposed to direct storage.googleapis.com access. If it isn't, this
  # block is inert for the URL the player actually uses (cdn_base_url).
  # Check this against the real cdn_base_url at first apply.
  #
  # SECOND, INDEPENDENT FAILURE MODE: Cloud CDN does not vary its cache on
  # the `Origin` header by default. Even where GCS emits correct CORS
  # headers, a response cached for one Origin can be served to a later
  # requester from a different Origin, carrying the wrong
  # Access-Control-Allow-Origin value — the browser then rejects it. This
  # needs a cache key policy (or Vary: Origin honoured end-to-end) to be
  # actually safe, and is not yet done.
  cors {
    origin          = var.client_origins
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type", "Range", "Content-Range", "Accept-Ranges"]
    max_age_seconds = 3600
  }

  depends_on = [google_project_service.enabled]
}

# Audio is world-readable by design: unauthenticated listening is a product
# requirement, so signed URLs would add cost and defeat shared caching without
# protecting anything. See spec D1.
resource "google_storage_bucket_iam_member" "songs_public_read" {
  bucket = google_storage_bucket.songs.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

resource "google_compute_backend_bucket" "songs" {
  name        = "pulsefm-songs-backend"
  bucket_name = google_storage_bucket.songs.name
  enable_cdn  = true

  # Tracks are write-once and the uploader stamps each object with
  # `Cache-Control: public, max-age=31536000, immutable`. Deferring to that
  # keeps cache lifetime defined in one place — the thing that knows the
  # content never changes — instead of a CDN cap that silently overrides it.
  cdn_policy {
    cache_mode        = "USE_ORIGIN_HEADERS"
    negative_caching  = true
    serve_while_stale = 86400
  }
}

resource "google_compute_global_address" "cdn" {
  name = "pulsefm-cdn-ip"

  # The other compute resources reach compute.googleapis.com transitively via
  # the bucket; this one references nothing, so it needs the edge declared.
  depends_on = [google_project_service.enabled]
}

resource "google_compute_url_map" "cdn" {
  name            = "pulsefm-cdn"
  default_service = google_compute_backend_bucket.songs.id
}

resource "google_compute_target_http_proxy" "cdn" {
  name    = "pulsefm-cdn-proxy"
  url_map = google_compute_url_map.cdn.id
}

resource "google_compute_global_forwarding_rule" "cdn" {
  name       = "pulsefm-cdn-rule"
  target     = google_compute_target_http_proxy.cdn.id
  ip_address = google_compute_global_address.cdn.address
  port_range = "80"
}
