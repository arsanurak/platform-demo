# Plan-level tests for stage 2. The helm provider is mocked, so these need no
# cluster. Each run either plans the whole root or the per-cluster module.

mock_provider "helm" {
  alias = "old"
}

mock_provider "helm" {
  alias = "new"
}

mock_provider "helm" {}

variables {
  kubeconfig_path = "/tmp/platform-demo/kubeconfig"
}

run "bootstraps_both_clusters_from_their_own_folder" {
  command = plan

  assert {
    condition     = output.root_app_paths == { old = "gitops/bootstrap/old", new = "gitops/bootstrap/new" }
    error_message = "Each cluster's root app must point at gitops/bootstrap/<cluster>."
  }
}

run "argo_cd_comes_from_the_pinned_chart" {
  command = plan

  module {
    source = "./modules/argocd"
  }

  variables {
    cluster      = "old"
    repo_url     = "https://github.com/example/platform-demo.git"
    git_revision = "main"
  }

  assert {
    condition     = helm_release.argocd.chart == "argo-cd" && helm_release.argocd.repository == "https://argoproj.github.io/argo-helm"
    error_message = "Argo CD must come from the official argo-helm chart."
  }

  assert {
    condition     = can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", helm_release.argocd.version))
    error_message = "The Argo CD chart must be pinned to an exact version."
  }

  assert {
    condition     = helm_release.argocd.namespace == "argocd" && helm_release.argocd.create_namespace
    error_message = "Argo CD must install into its own argocd namespace."
  }
}

run "root_app_holds_the_cluster_applicationset" {
  command = plan

  module {
    source = "./modules/argocd"
  }

  variables {
    cluster      = "new"
    repo_url     = "https://github.com/example/platform-demo.git"
    git_revision = "ticket-2"
  }

  assert {
    condition     = helm_release.root_app.chart == "argocd-apps" && can(regex("^[0-9]+\\.[0-9]+\\.[0-9]+$", helm_release.root_app.version))
    error_message = "The root app must come from the pinned argocd-apps chart."
  }

  assert {
    condition = {
      for s in helm_release.root_app.set : s.name => s.value
      } == {
      "applications.root.source.repoURL"        = "https://github.com/example/platform-demo.git"
      "applications.root.source.targetRevision" = "ticket-2"
      "applications.root.source.path"           = "gitops/bootstrap/new"
    }
    error_message = "The root app must track this repo at the given revision, in the cluster's bootstrap folder."
  }

  assert {
    condition = alltrue([
      for op in yamldecode(yamldecode(helm_release.root_app.values[1]).applications.root.source.kustomize.patches[0].patch) :
      op.value == (endswith(op.path, "repoURL") ? "https://github.com/example/platform-demo.git" : "ticket-2")
    ])
    error_message = "The root app must patch the bootstrap ApplicationSet to track repo_url at git_revision."
  }
}
