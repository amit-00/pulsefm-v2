resource "google_storage_bucket" "songs" {
  name          = var.songs_bucket_name
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  # Load-bearing for playback, not just for the slice 4 analyser:
  # client/src/hooks/useAudioSlots.ts sets crossOrigin="anonymous" on the
  # <audio> element, which makes every track fetch a CORS request. A response
  # without Access-Control-Allow-Origin fails the load outright — no audio at
  # all. The slice 4 WebAudio analyser needs the same headers or it silently
  # reads zeros, but playback is the immediate reason this block exists.
  #
  # Tracks are served straight from storage.googleapis.com (ADR 0002), so this
  # bucket-level config is the one that applies, on the documented path. When a
  # CDN goes back in front, re-verify: it is not documented whether bucket CORS
  # is honoured through a backend_bucket, and Cloud CDN does not vary its cache
  # on Origin by default — a response cached for one origin can be served to
  # another carrying the wrong Access-Control-Allow-Origin.
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
#
# legacyObjectReader, NOT objectViewer — deliberate, please don't "fix" it.
# objectViewer carries storage.objects.list as well as .get, which makes the
# anonymous listing endpoints usable by anyone who knows the bucket name:
#
#   GET https://storage.googleapis.com/<bucket>?list-type=2
#
# That returns the entire object inventory with sizes and creation timestamps,
# rather than just the track currently being broadcast. legacyObjectReader
# grants .get without .list, so single-object reads and Range requests — all
# playback actually needs — are unaffected. Google recommends precisely this
# swap for public buckets:
# https://cloud.google.com/storage/docs/access-control/making-data-public
#
# This matters more once generation lands: per spec D5 the worker uploads a
# track to GCS *before* flipping its Firestore document to status=ready, so a
# listable bucket exposes unreleased tracks ahead of their rotation.
resource "google_storage_bucket_iam_member" "songs_public_read" {
  bucket = google_storage_bucket.songs.name
  role   = "roles/storage.legacyObjectReader"
  member = "allUsers"
}
