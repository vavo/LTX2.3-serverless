# CI/CD

## Validation

[`test.yml`](../.github/workflows/test.yml) runs on pushes and pull requests. It validates shell syntax/tests, JSON, Python syntax, focused workflow/payload tests, GitHub Actions YAML, and Docker bake definitions.

It does not build the full image or execute a GPU workflow. Treat a successful check as the host-side gate, then run the GPU release gate in the [development guide](development.md#gpu-release-gate).

## Development images

[`dev.yml`](../.github/workflows/dev.yml) is manual-only. It builds and pushes the primary `ltx2-5-distilled-int8` target using the current ref name as the release tag component.

## Releases

[`release.yml`](../.github/workflows/release.yml) uses Changesets with Node.js 24 and pnpm 11:

1. A changeset on `main` creates or updates the version PR.
2. Merging the generated `chore: version packages` commit reads the version from `package.json`.
3. The workflow builds and pushes the four-target matrix.
4. It updates the Docker Hub description and creates a GitHub release.

Release targets:

- `base`
- `base-cuda12-8-1`
- `ltx2-5-distilled-int8`
- `ltx2-5-distilled-int8-cu128`

Manual full-matrix and single-target builds live in [`manual-build-all.yml`](../.github/workflows/manual-build-all.yml) and [`manual-push-dockerhub.yml`](../.github/workflows/manual-push-dockerhub.yml).

## Repository configuration

Configure these GitHub Actions secrets:

| Secret | Purpose |
| --- | --- |
| `DOCKERHUB_USERNAME` | Docker Hub login username. |
| `DOCKERHUB_TOKEN` | Docker Hub token with push access. |

Configure these repository variables:

| Variable | Purpose |
| --- | --- |
| `DOCKERHUB_REPO` | Docker Hub namespace. |
| `DOCKERHUB_IMG` | Image repository name. |

Hugging Face credentials are runtime secrets, not image-build secrets: model weights are downloaded to the persistent volume on worker startup and are never baked into release layers.
