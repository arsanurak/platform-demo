# Stage 1: the old and new kind clusters, and nothing inside them.
# Argo CD goes on in stage 2 (../argocd), a separate apply, because the helm
# and kubernetes providers can't be configured from a cluster created in the
# same apply.

locals {
  clusters = toset(["old", "new"])
}

resource "kind_cluster" "this" {
  for_each = local.clusters

  name            = each.key
  node_image      = var.node_image
  kubeconfig_path = var.kubeconfig_path
  wait_for_ready  = true

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    # One node per cluster keeps both clusters inside about 8 GB of Docker memory.
    node {
      role = "control-plane"
    }
  }
}
