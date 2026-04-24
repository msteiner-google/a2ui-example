terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    null = {
      source  = "hashicorp/null"
      version = "~> 3.2"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable necessary APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "discoveryengine.googleapis.com"
  ])
  service            = each.key
  disable_on_destroy = false
}

# Artifact Registry to store the image
resource "google_artifact_registry_repository" "agent_repo" {
  location      = var.region
  repository_id = "adk2-agent-repo"
  description   = "Docker repository for A2UI agent"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# Build the docker image via Cloud Build
resource "null_resource" "build_image" {
  triggers = {
    dockerfile = filemd5("../Dockerfile")
    pyproject  = filemd5("../pyproject.toml")
    uv_lock    = filemd5("../uv.lock")
    src_folder = sha1(join("", [for f in fileset("../src", "**") : filesha1("../src/${f}")]))
  }

  provisioner "local-exec" {
    command = "gcloud builds submit .. --config=../cloudbuild.yaml --substitutions=_IMAGE_NAME=${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agent_repo.repository_id}/adk2-agent:latest --project ${var.project_id} --quiet"
  }

  depends_on = [google_artifact_registry_repository.agent_repo]
}

# Cloud Run service
resource "google_cloud_run_v2_service" "agent_service" {
  name     = "adk2-agent-service"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    annotations = {
      "force-deploy" = null_resource.build_image.id
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agent_repo.repository_id}/adk2-agent:latest"

      env {
        name  = "A2UI_PROTOCOL_VERSION"
        value = "0.8"
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }

      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }

      resources {
        limits = {
          memory = "1024Mi"
          cpu    = "1"
        }
      }

      ports {
        container_port = 8080
      }
    }
  }

  depends_on = [null_resource.build_image]
}

data "google_project" "project" {
  project_id = var.project_id
}

# Allow Gemini Enterprise invocation
resource "google_cloud_run_service_iam_member" "invoker" {
  location = google_cloud_run_v2_service.agent_service.location
  project  = google_cloud_run_v2_service.agent_service.project
  service  = google_cloud_run_v2_service.agent_service.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-discoveryengine.iam.gserviceaccount.com"
}

output "service_url" {
  value = google_cloud_run_v2_service.agent_service.uri
}

