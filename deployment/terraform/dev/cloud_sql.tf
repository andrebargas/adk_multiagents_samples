# --- Cloud SQL PostgreSQL Instance for Development ---
resource "google_sql_database_instance" "postgres_instance" {
  project = var.dev_project_id
  name = "${var.project_name}-postgres-dev"
  region = var.region
  database_version = var.postgres_version
  deletion_protection = false
  root_password = var.postgres_admin_password

  settings {
    tier    = "db-f1-micro" # Smallest shared-core instance type
    
    # Network
    ip_configuration {
      ipv4_enabled = true
    }
    # Storage
    disk_type = "PD_SSD"
    disk_size = 10
    backup_configuration {
      enabled = false
    }
    # Availability Type
    availability_type = "ZONAL"
  }

  depends_on = [
    resource.google_project_service.services
  ]
}

resource "google_sql_user" "users" {
  name     = var.postgres_user
  instance = google_sql_database_instance.postgres_instance.name
  project  = var.dev_project_id
  password = var.postgres_password

  depends_on = [
    google_sql_database_instance.postgres_instance
  ]
}

resource "google_sql_database" "sessions_db" {
  name     = var.postgres_session_db
  instance = google_sql_database_instance.postgres_instance.name
  project  = var.dev_project_id
}


