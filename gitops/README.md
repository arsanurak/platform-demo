# GitOps area

Argo CD applications and ApplicationSets that Argo CD syncs onto the old and new clusters. See `docs/adr/0001-one-repo-for-iac-and-gitops.md` for why this lives next to `iac/`.

| Folder | What it holds |
| --- | --- |
| `bootstrap/<cluster>/` | The ApplicationSet that each cluster's root app syncs. It makes one Application per folder under `clusters/<cluster>/`. |
| `clusters/<cluster>/<name>/` | Plain manifests for one Application, deployed into a namespace named after the folder. |
| `clusters/<cluster>/gateway/` | The cluster's `web` Gateway, served by cloud-provider-kind. |
| `clusters/old/app01/` | **App** `app01`: podinfo, reached through the gateway with `Host: app01.example.com`. |

Moving an **App** between clusters is moving its folder from `clusters/old/` to `clusters/new/`.

`make check-gitops` validates every manifest here with kubeconform, against pinned Kubernetes schemas and pinned Argo CD and Gateway API CRD schemas. A kind with no schema fails the check. It also runs kubeconform on the known-bad files in `tests/fixtures/gitops-invalid/` and fails unless each one is rejected.
