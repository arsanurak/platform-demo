# Plan-level tests for stage 1. The kind provider is mocked, so these need no
# Docker and create no clusters.

mock_provider "kind" {}

variables {
  kubeconfig_path = "/tmp/platform-demo/kubeconfig"
}

run "creates_the_old_and_new_clusters" {
  command = plan

  assert {
    condition     = toset(keys(kind_cluster.this)) == toset(["old", "new"])
    error_message = "Stage 1 must create exactly two kind clusters, old and new."
  }

  assert {
    condition     = toset([for c in kind_cluster.this : c.name]) == toset(["old", "new"])
    error_message = "The kind cluster names must be old and new."
  }
}

run "node_image_is_pinned_by_digest" {
  command = plan

  assert {
    condition     = alltrue([for c in kind_cluster.this : can(regex("^kindest/node:v[0-9.]+@sha256:[0-9a-f]{64}$", c.node_image))])
    error_message = "Every cluster must use a kindest/node image pinned by tag and digest."
  }
}

run "kubeconfig_goes_to_the_given_path" {
  command = plan

  assert {
    condition     = alltrue([for c in kind_cluster.this : c.kubeconfig_path == "/tmp/platform-demo/kubeconfig"])
    error_message = "Both clusters must write their context to the kubeconfig the make targets use."
  }

  assert {
    condition     = output.kube_contexts == { old = "kind-old", new = "kind-new" }
    error_message = "Stage 2 finds each cluster by its kind-<name> context."
  }
}

run "waits_for_the_control_plane" {
  command = plan

  assert {
    condition     = alltrue([for c in kind_cluster.this : c.wait_for_ready])
    error_message = "Stage 1 must not finish before each control plane is ready, or stage 2 fails."
  }
}
