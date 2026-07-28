output "cdn_base_url" {
  value       = "http://${google_compute_global_address.cdn.address}"
  description = "Base URL for audio objects. Slice 4 puts a managed certificate and domain in front of this."
}

output "songs_bucket_name" {
  value       = google_storage_bucket.songs.name
  description = "Bucket holding encoded tracks."
}
