variable "region" {
  description = "AWS region the cluster would run in."
  type        = string
  default     = "eu-west-1"
}

variable "availability_zones" {
  description = "Availability zones to spread subnets across. One subnet of each kind per zone."
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}

variable "cluster_name" {
  description = "Name of the EKS cluster. Also prefixes the names of its supporting resources."
  type        = string
  default     = "new"
}

variable "kubernetes_version" {
  description = "Kubernetes minor version of the control plane."
  type        = string
  default     = "1.35"
}

variable "vpc_cidr" {
  description = "CIDR block of the cluster VPC. Subnets are carved from it."
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_instance_types" {
  description = "EC2 instance types for the managed node group."
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_count" {
  description = "Minimum, desired and maximum number of nodes."
  type = object({
    min     = number
    desired = number
    max     = number
  })
  default = {
    min     = 1
    desired = 2
    max     = 3
  }
}

variable "admin_role_arn" {
  description = "IAM role that gets cluster admin through an EKS access entry. A placeholder by default."
  type        = string
  default     = "arn:aws:iam::000000000000:role/platform-admin"

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:iam::[0-9]{12}:role/.+$", var.admin_role_arn))
    error_message = "admin_role_arn must be an IAM role ARN."
  }
}

variable "permissions_boundary_arn" {
  description = "Permission boundary every role here carries. The guardrails' Execution role can only create roles that have it (see iac/guardrails)."
  type        = string
  default     = "arn:aws:iam::000000000000:policy/platform-demo-boundary"

  validation {
    condition     = can(regex("^arn:aws[a-z-]*:iam::[0-9]{12}:policy/.+$", var.permissions_boundary_arn))
    error_message = "Must be an IAM policy ARN."
  }
}
