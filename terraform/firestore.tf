resource "google_firestore_database" "default" {
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  # location_id is ForceNew: changing it destroys and recreates the database,
  # taking every song and station document with it.
  lifecycle {
    prevent_destroy = true
  }

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
