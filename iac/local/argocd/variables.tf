variable "kubeconfig_path" {
  description = "Kubeconfig file stage 1 wrote the kind-old and kind-new contexts to."
  type        = string
}

variable "repo_url" {
  description = "Git URL Argo CD syncs from. Point it at your fork to try changes."
  type        = string
  default     = "https://github.com/arsanurak/platform-demo.git"
}

variable "git_revision" {
  description = "Branch, tag or commit of repo_url that Argo CD tracks."
  type        = string
  default     = "main"
}
