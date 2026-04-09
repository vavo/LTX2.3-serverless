# CI/CD

This project includes GitHub Actions workflows to automatically build and deploy Docker images to Docker Hub.

## Automatic Deployment to Docker Hub with GitHub Actions

The repository contains two main publishing workflows located in the `.github/workflows` directory:

- [`dev.yml`](../.github/workflows/dev.yml): Builds and pushes the default LTX image target (`ltx2-3-distilled`) for development snapshots.
- [`release.yml`](../.github/workflows/release.yml): Builds and pushes the release matrix for the targets that matter to this repo: `base`, `base-cuda12-8-1`, `base-cuda13-0`, `ltx2-3-distilled`, `ltx2-3-distilled-fp8`, and `ltx2-3-distilled-cuda13`.

Additional manual workflows are available when you need to rebuild the full matrix or push one target on demand:

- [`manual-build-all.yml`](../.github/workflows/manual-build-all.yml)
- [`manual-push-dockerhub.yml`](../.github/workflows/manual-push-dockerhub.yml)

### Configuration for Your Fork

If you have forked this repository and want to use these actions to publish images to your own Docker Hub account, you need to configure the following in your GitHub repository settings:

1.  **Secrets** (`Settings > Secrets and variables > Actions > New repository secret`):

    | Secret Name                | Description                                                                | Example Value       |
    | -------------------------- | -------------------------------------------------------------------------- | ------------------- |
    | `DOCKERHUB_USERNAME`       | Your Docker Hub username.                                                  | `your-dockerhub-id` |
    | `DOCKERHUB_TOKEN`          | Your Docker Hub access token with read/write permissions.                  | `dckr_pat_...`      |
    | `HUGGINGFACE_ACCESS_TOKEN` | Your READ access token from Hugging Face for LTX and other model downloads. | `hf_...`            |

2.  **Variables** (`Settings > Secrets and variables > Actions > New repository variable`):

    | Variable Name    | Description                                                                  | Example Value              |
    | ---------------- | ---------------------------------------------------------------------------- | -------------------------- |
    | `DOCKERHUB_REPO` | The target repository (namespace) on Docker Hub where images will be pushed. | `your-dockerhub-id`        |
    | `DOCKERHUB_IMG`  | The base name for the image to be pushed to Docker Hub.                      | `my-custom-ltx-worker` |

With these secrets and variables configured, the actions will push the built images (for example `your-dockerhub-id/my-custom-ltx-worker:dev-ltx2.3-distilled-cu128` or `your-dockerhub-id/my-custom-ltx-worker:1.0.0-ltx2.3-distilled-cu128`) to your Docker Hub account when triggered.
