# Both services read Firestore; only radio-service writes it.
resource "google_project_iam_member" "radio_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.radio.email}"
}

resource "google_project_iam_member" "station_api_firestore_read" {
  project = var.project_id
  role    = "roles/datastore.viewer"
  member  = "serviceAccount:${google_service_account.station_api.email}"
}

resource "google_project_iam_member" "radio_enqueue" {
  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.radio.email}"
}

# radio-service creates tasks that run as the tick invoker, which requires
# impersonation rights on that account.
resource "google_service_account_iam_member" "radio_acts_as_tick_invoker" {
  service_account_id = google_service_account.tick_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.radio.email}"
}

# The only identity allowed to invoke radio-service.
resource "google_cloud_run_v2_service_iam_member" "tick_invoker" {
  name     = google_cloud_run_v2_service.radio.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.tick_invoker.email}"
}

# station-api is public in slices 0-1. Slice 3 replaces allUsers with the API
# Gateway service account.
resource "google_cloud_run_v2_service_iam_member" "station_api_public" {
  name     = google_cloud_run_v2_service.station_api.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
