variable "cluster" {
  description = "Cluster name, old or new. Picks the gitops/bootstrap/<cluster> folder the root app syncs."
  type        = string

  validation {
    condition     = contains(["old", "new"], var.cluster)
    error_message = "cluster must be old or new."
  }
}

variable "repo_url" {
  description = "Git URL Argo CD syncs from."
  type        = string
}

variable "git_revision" {
  description = "Branch, tag or commit of repo_url that Argo CD tracks."
  type        = string
}
