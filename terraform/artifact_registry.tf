resource "google_artifact_registry_repository" "services" {
  repository_id = "pulsefm"
  location      = var.region
  format        = "DOCKER"
  description   = "PulseFM v2 service images."

  depends_on = [google_project_service.enabled]
}
