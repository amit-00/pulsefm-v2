output "cdn_base_url" {
  value       = "http://${google_compute_global_address.cdn.address}"
  description = "Base URL for audio objects. Slice 4 puts a managed certificate and domain in front of this."
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
