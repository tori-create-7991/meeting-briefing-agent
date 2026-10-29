variable "project_id" {
  description = "Project created by infra/bootstrap."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Agent Runtime and Artifact Registry."
  type        = string
  default     = "us-central1"
}

variable "org_id" {
  description = "Numeric organization ID; part of the Agent Identity principal."
  type        = string
}

variable "workspace_subject" {
  description = "Workspace user whose Calendar and Docs the agent reads (domain-wide delegation subject)."
  type        = string
}

variable "invoker_members" {
  description = "IAM members allowed to call the MCP front, e.g. [\"user:me@example.org\"]. Never allUsers."
  type        = list(string)

  validation {
    condition     = length(var.invoker_members) > 0 && !contains(var.invoker_members, "allUsers") && !contains(var.invoker_members, "allAuthenticatedUsers")
    error_message = "invoker_members must list specific principals, not allUsers or allAuthenticatedUsers."
  }
}

variable "mcp_image" {
  description = "MCP front image. The first apply can use the public placeholder before scripts/build_mcp_image.sh has run."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "agent_source_archive" {
  description = "Path to the archive built by scripts/build_agent_source.sh."
  type        = string
  default     = "../../dist/agent_source.tar.gz"
}

variable "class_methods_file" {
  description = "Path to the class_methods spec built by scripts/build_agent_source.sh."
  type        = string
  default     = "../../dist/class_methods.json"
}

variable "briefing_model" {
  description = "Gemini model ID used by the briefing writer."
  type        = string
  default     = "gemini-3.5-flash"
}

variable "briefing_language" {
  description = "Language the briefing is written in."
  type        = string
  default     = "ja"
}

variable "briefing_timezone" {
  description = "Timezone used to turn a date into a day window."
  type        = string
  default     = "Asia/Tokyo"
}

variable "agent_min_instances" {
  description = "Minimum Agent Runtime instances. 0 avoids idle cost at the price of cold starts."
  type        = number
  default     = 0
}

variable "agent_max_instances" {
  description = "Maximum Agent Runtime instances."
  type        = number
  default     = 2
}

variable "agent_cpu" {
  description = "vCPUs per Agent Runtime instance (the runtime default is 4)."
  type        = string
  default     = "1"
  validation {
    condition     = contains(["1", "2", "4", "6", "8"], var.agent_cpu)
    error_message = "agent_cpu must be one of 1, 2, 4, 6, 8."
  }
}

variable "agent_memory" {
  description = "Memory per Agent Runtime instance, in whole Gi (the runtime default is 4Gi)."
  type        = string
  default     = "2Gi"
  validation {
    condition     = can(regex("^([1-9]|[12][0-9]|3[0-2])Gi$", var.agent_memory))
    error_message = "agent_memory must look like 2Gi (1Gi to 32Gi)."
  }
}

variable "runtime_identity" {
  description = "agent_identity (default) or service_account (fallback: a dedicated briefing-runtime service account)."
  type        = string
  default     = "agent_identity"

  validation {
    condition     = contains(["agent_identity", "service_account"], var.runtime_identity)
    error_message = "runtime_identity must be agent_identity or service_account."
  }
}
