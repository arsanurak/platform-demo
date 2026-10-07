variable "region" {
  description = "AWS region the Execution role may work in."
  type        = string
  default     = "eu-west-1"
}

variable "github_repository" {
  description = "The GitHub repository, as owner/name, whose main branch may assume the Execution role."
  type        = string
  default     = "example-org/platform-demo"

  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.github_repository))
    error_message = "Use an exact owner/name. A wildcard would let other repositories assume the role."
  }
}

variable "scp_target_id" {
  description = "Organization root, OU or account the payment lockout applies to. A placeholder."
  type        = string
  default     = "ou-0000-00000000"
}
