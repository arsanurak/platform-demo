# Local stack (kind)

The two Terraform roots `make up` applies to bring up the demo on your laptop. They are separate applies on purpose: the helm provider can't be configured from a cluster that the same apply creates, so creating the clusters and installing into them are two stages.

| Stage | Root | What it creates |
| --- | --- | --- |
| 1 | `clusters/` | The **Old cluster** and **New cluster** as kind clusters (`kind-old`, `kind-new` contexts in `build/kubeconfig`), one node each, node image pinned by digest |
| 2 | `argocd/` | On each cluster: Argo CD from the `argo-cd` chart, and a root app from the `argocd-apps` chart that syncs `gitops/bootstrap/<cluster>/` |

The root app's folder holds one ApplicationSet, which creates an Application for every folder under `gitops/clusters/<cluster>/`. From then on Argo CD syncs everything from git; no script applies manifests.

Between the stages `make up` starts [cloud-provider-kind](https://github.com/kubernetes-sigs/cloud-provider-kind) in a container. It installs the Gateway API CRDs and implements the `cloud-provider-kind` GatewayClass, so each cluster's `web` Gateway gets an address. There is no ingress controller.

- Chart versions are pinned in `argocd/charts.json`, read by both Terraform and `make helm-template`.
- Helm values are in `argocd/values/`. Terraform sets only the per-cluster path and the git revision; CI renders the same files with `helm template`.
- Set `GIT_REVISION` to make Argo CD track another branch or commit: `GIT_REVISION=my-branch make up`. The root app renders `gitops/bootstrap/<cluster>/` with Kustomize and patches the ApplicationSet there to the same repo URL and revision; `make wave-N` applies its wave at `GIT_REVISION` too.

## Checks

These run on every pull request and need no Docker:

- `make validate` and `make test-tf`: `terraform validate`, and `terraform test` with the kind and helm providers mocked (`*/tests/*.tftest.hcl`).
- `make helm-template`: renders both charts with these values and validates the output with kubeconform.
- `make check-gitops`: validates everything under `gitops/` with kubeconform, Argo CD and Gateway API CRD schemas included.

`make down` deletes both clusters through stage 1, drops stage 2's local state (the releases went with the clusters) and removes the cloud-provider-kind containers.
