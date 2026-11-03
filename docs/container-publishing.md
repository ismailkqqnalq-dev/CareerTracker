# Container publishing

The Publish container workflow builds PR images without registry credentials or publishing. A published, non-prerelease GitHub Release with a vMAJOR.MINOR.PATCH tag publishes the tagged commit only if it belongs to main's history.

Before creating a Release, confirm CI passed for its target commit. Create the release from the reviewed main commit. No image is published merely by merging a PR.

Images use version tags, for example:
```sh
docker pull ghcr.io/ismailkqqnalq-dev/careertracker:v0.1.0
```
No latest tag is updated. Do not reuse release tags.

The job uses its temporary GITHUB_TOKEN with contents: read and packages: write. No personal token or Docker Hub account is needed. Checkout is pinned to a commit. Each image is checked for non-root execution and absence of /app/.env and /app/careertracker.db before pushing.

GHCR normally creates new packages as private. This workflow does not change package visibility. Check the package's settings after first publication; making it public is a separate owner decision. Existing package permissions may affect publication.

This is the existing backend Dockerfile: it does not bundle the frontend or optional OCR engine. OCR requests return the documented unavailable error without the OCR extra. Supply DATABASE_URL and a valid JWT_SECRET_KEY at runtime through your deployment's secret mechanism; never bake them into an image. Apply database migrations deliberately before serving traffic. Publishing does not deploy a server.

The pull command above requires registry authentication while the package is private. Use a version tag or digest when deploying. The workflow and PR CI validate builds; registry authentication/push can only be verified at the first actual release.
