# GitOps area

Argo CD applications and ApplicationSets that Argo CD syncs onto the old and new clusters. See `docs/adr/0001-one-repo-for-iac-and-gitops.md` for why this lives next to `iac/`.

| Folder | What it holds |
| --- | --- |
| `bootstrap/<cluster>/` | The ApplicationSet that each cluster's root app syncs. It makes one Application per folder under `clusters/<cluster>/`, and on old also one per App under `apps/`. |
| `clusters/<cluster>/<name>/` | Plain manifests for one Application, deployed into a namespace named after the folder. |
| `clusters/<cluster>/gateway/` | The cluster's `web` Gateway, served by cloud-provider-kind. |
| `waves.toml` | The one definition of the **Apps**, which App calls which, and the **Waves** that move them. Hand-edited. Its `[parity]` table sets the endpoints and headers `make parity` compares. |
| `apps/<app>/` | Generated. **App** `<app>`: podinfo, non-root with a read-only root filesystem, reached through the gateway with `Host: <app>.example.com`. `app05` calls `app04` through podinfo's `--backend-url`. |
| `waves/wave-<n>/` | Generated. An ApplicationSet that puts wave `n`'s **Apps** on the new cluster. `make wave-<n>` applies it. |

The old cluster runs every **App** from the start. The new cluster gets them a **Wave** at a time: `make wave-N` applies wave N's ApplicationSet to new, after checking that every earlier wave is healthy there.

`scripts/generate-waves.py` writes `apps/` and `waves/` from `waves.toml`, so adding an App or reordering the waves is a one-line edit. It refuses a definition where an App is in no wave, in two waves, or in the same or an earlier wave than an App it calls. Run `make waves` after editing and commit the output. `make check-waves`, part of `make check` and CI, regenerates and fails if the committed files differ.

`make check-gitops` validates every manifest here with kubeconform, against pinned Kubernetes schemas and pinned Argo CD and Gateway API CRD schemas. A kind with no schema fails the check. It also runs kubeconform on the known-bad files in `tests/fixtures/gitops-invalid/` and fails unless each one is rejected.
