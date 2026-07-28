resource "google_service_account" "radio" {
  account_id   = "pulsefm-radio"
  display_name = "PulseFM radio-service runtime"

  depends_on = [google_project_service.enabled]
}

resource "google_service_account" "station_api" {
  account_id   = "pulsefm-station-api"
  display_name = "PulseFM station-api runtime"

  depends_on = [google_project_service.enabled]
}

# Cloud Tasks mints OIDC tokens as this identity to call radio-service /tick.
resource "google_service_account" "tick_invoker" {
  account_id   = "pulsefm-tick-invoker"
  display_name = "PulseFM Cloud Tasks tick invoker"

  depends_on = [google_project_service.enabled]
}
