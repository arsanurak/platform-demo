variable "account_id" {
  description = "AWS account the guardrails live in. A placeholder: this code is never applied."
  type        = string
  default     = "000000000000"
}

variable "region" {
  description = "The only region the Execution role may work in."
  type        = string
  default     = "eu-west-1"
}

variable "github_repository" {
  description = "The GitHub repository, as owner/name, whose main branch may assume the Execution role."
  type        = string
  default     = "example-org/platform-demo"
}

variable "name_prefix" {
  description = "Prefix for the names of the role and its policies."
  type        = string
  default     = "platform-demo"
}
