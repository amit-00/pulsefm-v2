variable "project_id" {
  type        = string
  description = "GCP project id hosting PulseFM v2."
}

variable "region" {
  type        = string
  description = "Region for Cloud Run, Cloud Tasks, and Artifact Registry. Does NOT govern Firestore — see firestore_location."
  default     = "us-central1"
}

variable "firestore_location" {
  type        = string
  description = "Firestore location. Deliberately separate from var.region: location_id is ForceNew, so changing it destroys and recreates the database."
  default     = "us-central1"
}

variable "songs_bucket_name" {
  type        = string
  description = "Globally unique name for the public audio bucket."
}

variable "client_origins" {
  type        = list(string)
  description = "Origins allowed to read audio with CORS (needed by the slice 4 analyser)."
  default     = ["http://localhost:5173"]
}

variable "tick_url" {
  type        = string
  description = "Absolute URL of radio-service's /tick endpoint. Empty on the first apply — Cloud Run's URL is not known until the service exists. Read `terraform output radio_service_url` after the first apply, set this to \"<that url>/tick\", and apply again."
  default     = ""
}
