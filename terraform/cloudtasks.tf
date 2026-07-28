resource "google_cloud_tasks_queue" "radio" {
  name     = "radio-queue"
  location = var.region

  rate_limits {
    max_dispatches_per_second = 5
    max_concurrent_dispatches = 5
  }

  # A tick that fails is superseded by the next one; long retry storms would
  # only replay stale versions, which the version guard already discards.
  retry_config {
    max_attempts       = 5
    min_backoff        = "1s"
    max_backoff        = "10s"
    max_retry_duration = "60s"
  }

  # References only var.region: no reference chain to google_project_service.enabled.
  depends_on = [google_project_service.enabled]
}
