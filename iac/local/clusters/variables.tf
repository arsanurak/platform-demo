variable "kubeconfig_path" {
  description = "Kubeconfig file both clusters write their context to. `make up` passes build/kubeconfig, so your own ~/.kube/config is left alone."
  type        = string
}

variable "node_image" {
  description = "kindest/node image for every cluster, pinned by tag and digest. It must be one the pinned kind provider's kind release supports."
  type        = string
  default     = "kindest/node:v1.35.0@sha256:452d707d4862f52530247495d180205e029056831160e22870e37e3f6c1ac31f"
}
