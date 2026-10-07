# Argo CD on one cluster, plus a root app that syncs gitops/bootstrap/<cluster>.
# That folder holds the ApplicationSet which creates every other Application,
# so after this apply Argo CD does the rest from git.

locals {
  charts = jsondecode(file("${path.module}/../../charts.json"))
  values = "${path.module}/../../values"

  # gitops/bootstrap/<cluster>/applicationset.yaml says main and this repo; the
  # root app renders that folder with Kustomize and points the ApplicationSet's
  # git generator and template at repo_url and git_revision instead. That way a
  # fork, a branch or CI's commit under test is what every App comes from.
  bootstrap_patches = [{
    target = { group = "argoproj.io", kind = "ApplicationSet", name = "cluster-apps" }
    patch = yamlencode([
      { op = "replace", path = "/spec/generators/0/git/repoURL", value = var.repo_url },
      { op = "replace", path = "/spec/generators/0/git/revision", value = var.git_revision },
      { op = "replace", path = "/spec/template/spec/source/repoURL", value = var.repo_url },
      { op = "replace", path = "/spec/template/spec/source/targetRevision", value = var.git_revision },
    ])
  }]
}

resource "helm_release" "argocd" {
  name             = "argocd"
  namespace        = "argocd"
  create_namespace = true
  repository       = local.charts.repository
  chart            = "argo-cd"
  version          = local.charts["argo-cd"]
  values           = [file("${local.values}/argo-cd.yaml")]
  wait             = true
  timeout          = 600
}

resource "helm_release" "root_app" {
  name       = "root-app"
  namespace  = "argocd"
  repository = local.charts.repository
  chart      = "argocd-apps"
  version    = local.charts["argocd-apps"]
  values = [
    file("${local.values}/argocd-apps.yaml"),
    yamlencode({ applications = { root = { source = { kustomize = { patches = local.bootstrap_patches } } } } }),
  ]

  # Only what differs per cluster or per checkout is set here; the rest is in
  # values/argocd-apps.yaml, which CI renders with `helm template`.
  set = [
    {
      name  = "applications.root.source.repoURL"
      value = var.repo_url
    },
    {
      name  = "applications.root.source.targetRevision"
      value = var.git_revision
    },
    {
      name  = "applications.root.source.path"
      value = "gitops/bootstrap/${var.cluster}"
    },
  ]

  # The Application CRD ships with the argo-cd chart.
  depends_on = [helm_release.argocd]
}
