terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

variable "project_id" {
  type = string
}
variable "region" {
  type    = string
  default = "us-central1"
}
variable "service_name" {
  type    = string
  default = "sentinelops"
}
variable "container_image" {
  type        = string
  description = "Published Artifact Registry image URI"
}
variable "runbook_bucket_name" {
  type = string
}
variable "dataset_id" {
  type    = string
  default = "sentinelops"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "apis" {
  for_each = toset(["run.googleapis.com", "storage.googleapis.com", "bigquery.googleapis.com", "cloudtrace.googleapis.com", "artifactregistry.googleapis.com", "secretmanager.googleapis.com"])
  project = var.project_id
  service = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "runbooks" {
  name = var.runbook_bucket_name
  location = var.region
  uniform_bucket_level_access = true
  public_access_prevention = "enforced"
  force_destroy = false
  depends_on = [google_project_service.apis]
}

resource "google_bigquery_dataset" "sentinelops" {
  dataset_id = var.dataset_id
  location = var.region
  delete_contents_on_destroy = false
  depends_on = [google_project_service.apis]
}

resource "google_service_account" "runtime" {
  account_id = "${var.service_name}-runtime"
  display_name = "SentinelOps Cloud Run runtime"
}

resource "google_secret_manager_secret" "api_key" {
  secret_id = "${var.service_name}-api-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "api_key_accessor" {
  secret_id = google_secret_manager_secret.api_key.id
  role = "roles/secretmanager.secretAccessor"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "trace_writer" {
  project = var.project_id
  role = "roles/cloudtrace.agent"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_storage_bucket_iam_member" "runbook_reader" {
  bucket = google_storage_bucket.runbooks.name
  role = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_bigquery_dataset_iam_member" "data_viewer" {
  dataset_id = google_bigquery_dataset.sentinelops.dataset_id
  project = var.project_id
  role = "roles/bigquery.dataViewer"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_bigquery_job_user" "query_user" {
  project = var.project_id
  role = "roles/bigquery.jobUser"
  member = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_cloud_run_v2_service" "api" {
  name = var.service_name
  location = var.region
  deletion_protection = true
  template {
    service_account = google_service_account.runtime.email
    containers {
      image = var.container_image
      ports { container_port = 8080 }
      env { name = "ENVIRONMENT", value = "production" }
      env { name = "GOOGLE_CLOUD_PROJECT", value = var.project_id }
      env { name = "BIGQUERY_DATASET", value = var.dataset_id }
      env { name = "GCS_RUNBOOK_BUCKET", value = google_storage_bucket.runbooks.name }
      env {
        name = "API_KEY"
        value_source {
          secret_key_ref {
            secret = google_secret_manager_secret.api_key.secret_id
            version = "latest"
          }
        }
      }
      resources { limits = { cpu = "1", memory = "512Mi" } }
    }
    scaling { min_instance_count = 0, max_instance_count = 10 }
  }
  depends_on = [google_project_service.apis]
}

output "service_uri" {
  value = google_cloud_run_v2_service.api.uri
}
output "dataset_id" {
  value = google_bigquery_dataset.sentinelops.dataset_id
}
