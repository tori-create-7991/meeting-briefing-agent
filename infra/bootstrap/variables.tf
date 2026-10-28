variable "project_id" {
  description = "ID of the new project (globally unique)."
  type        = string
}

variable "org_id" {
  description = "Numeric ID of the Google Workspace / Cloud organization."
  type        = string
}

variable "billing_account" {
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX)."
  type        = string
}

variable "region" {
  description = "Location of the state bucket."
  type        = string
  default     = "us-central1"
}

variable "deletion_policy" {
  description = "PREVENT blocks project deletion; set DELETE before destroying."
  type        = string
  default     = "PREVENT"

  validation {
    condition     = contains(["PREVENT", "DELETE", "ABANDON"], var.deletion_policy)
    error_message = "deletion_policy must be PREVENT, DELETE or ABANDON."
  }
}
