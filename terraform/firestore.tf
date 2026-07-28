resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.enabled]
}

# list_pool orders by playCount then lastPlayedAt with a status equality filter,
# which Firestore cannot serve from single-field indexes.
resource "google_firestore_index" "songs_pool" {
  database   = google_firestore_database.default.name
  collection = "songs"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }
  fields {
    field_path = "playCount"
    order      = "ASCENDING"
  }
  fields {
    field_path = "lastPlayedAt"
    order      = "ASCENDING"
  }
}
