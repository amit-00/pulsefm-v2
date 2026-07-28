locals {
  image_base = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.services.repository_id}"
}

# Images are pinned to :latest, so re-pushing the tag does NOT create a new
# Cloud Run revision — Terraform sees no config change. After a re-push, force
# one with `terraform apply -replace=google_cloud_run_v2_service.<name>` or
# `gcloud run deploy`. Slice 4 should move to digest-pinned images.

resource "google_cloud_run_v2_service" "radio" {
  name     = "radio-service"
  location = var.region

  # The control plane that spends money on GPUs is unreachable from the
  # internet; Cloud Tasks reaches it over internal ingress with OIDC.
  #
  # This works because the queue and this service are in the SAME project —
  # Google routes same-project Cloud Tasks calls as internal traffic without
  # them traversing a VPC. Move either to another project and ticking stops
  # with no Terraform-time error.
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.radio.email
    timeout         = "120s"

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = "${local.image_base}/radio-service:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      # Self-referencing google_cloud_run_v2_service.radio.uri here fails
      # `terraform plan` with "Error: Self-referential block" (uri is only
      # known after the service exists). Driven by var.tick_url instead: set
      # it after the first apply. See variable description for the sequence.
      env {
        name  = "TICK_URL"
        value = var.tick_url
      }
      env {
        name  = "TICK_SERVICE_ACCOUNT"
        value = google_service_account.tick_invoker.email
      }
      env {
        name  = "RADIO_QUEUE_NAME"
        value = google_cloud_tasks_queue.radio.name
      }
      env {
        name  = "RADIO_QUEUE_LOCATION"
        value = var.region
      }
    }
  }
}

resource "google_cloud_run_v2_service" "station_api" {
  name     = "station-api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.station_api.email
    timeout         = "30s"

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    containers {
      image = "${local.image_base}/station-api:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "CDN_BASE_URL"
        value = "http://${google_compute_global_address.cdn.address}"
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = join(",", var.client_origins)
      }
    }
  }
}
