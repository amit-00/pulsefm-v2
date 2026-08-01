output "audio_base_url" {
  value       = "https://storage.googleapis.com/${google_storage_bucket.songs.name}"
  description = "Base URL for audio objects, served straight from the bucket over HTTPS. See docs/adr/0002-no-cdn-for-audio.md for when to put a CDN back in front."
}

output "songs_bucket_name" {
  value       = google_storage_bucket.songs.name
  description = "Bucket holding encoded tracks."
}

output "station_api_url" {
  value       = google_cloud_run_v2_service.station_api.uri
  description = "Public base URL for the read API."
}

output "radio_service_url" {
  value       = google_cloud_run_v2_service.radio.uri
  description = "Internal base URL for the rotation clock."
}
