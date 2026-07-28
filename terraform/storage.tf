resource "google_storage_bucket" "songs" {
  name          = var.songs_bucket_name
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  # The analyser (slice 4) reads audio through WebAudio, which requires the
  # element to be crossOrigin="anonymous" and the response to carry CORS
  # headers. Without this the analyser silently returns zeros.
  cors {
    origin          = var.client_origins
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type", "Range"]
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

  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 3600
    max_ttl           = 86400
    client_ttl        = 3600
    negative_caching  = true
    serve_while_stale = 86400
  }
}

resource "google_compute_global_address" "cdn" {
  name = "pulsefm-cdn-ip"
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
