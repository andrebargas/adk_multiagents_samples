# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

variable "project_name" {
  type        = string
  description = "Project name used as a base for resource naming"
  default     = "data-explorer-agent"
}

variable "dev_project_id" {
  type        = string
  description = "**Dev** Google Cloud Project ID for resource deployment."
}

variable "region" {
  type        = string
  description = "Google Cloud region for resource deployment."
  default     = "us-central1"
}

variable "telemetry_logs_filter" {
  type        = string
  description = "Log Sink filter for capturing telemetry data. Captures logs with the `traceloop.association.properties.log_type` attribute set to `tracing`."
  default     = "labels.service_name=\"data-explorer-agent\" labels.type=\"agent_telemetry\""
}

variable "feedback_logs_filter" {
  type        = string
  description = "Log Sink filter for capturing feedback data. Captures logs where the `log_type` field is `feedback`."
  default     = "jsonPayload.log_type=\"feedback\" jsonPayload.service_name=\"data-explorer-agent\""
}


variable "agentengine_sa_roles" {
  description = "List of roles to assign to the Agent Engine app service account"

  type        = list(string)
  default = [
    "roles/aiplatform.user",
    "roles/discoveryengine.editor",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/storage.admin"
  ]
}

variable "cloud_run_app_roles" {
  description = "List of roles to assign to the Cloud Run app service account"

  type        = list(string)
  default = [
    "roles/aiplatform.user",
    "roles/discoveryengine.editor",
    "roles/logging.logWriter",
    "roles/cloudtrace.agent",
    "roles/storage.admin",
    "roles/cloudsql.client"
  ]
}

# --- Variables for Cloud SQL Instance ---
variable "postgres_version" {
  description = "PostgreSQL version for the instance."
  type        = string
  default     = "POSTGRES_15"
}

variable "postgres_admin_user" {
  description = "Postgres admin user for the instance."
  type        = string
  default     = "postgres"
}

variable "postgres_admin_password" {
  description = "Postgres admin password user for the instance."
  type        = string
}

variable "postgres_user" {
  description = "Postgres application user."
  type        = string
  default     = "data-explorer-agent-user"
}

variable "postgres_password" {
  description = "Postgres application user password."
  type        = string
  default     = "data-explorer-agent-user"
}

variable "postgres_session_db" {
  description = "PostgreSQL sessions database"
  type        = string
  default     = "data-explorer-agent-sessions"
}
