# Container publishing

The Publish container workflow builds and audits a candidate on pull requests without registry credentials or publishing. A published, non-prerelease GitHub Release with a `vMAJOR.MINOR.PATCH` tag publishes the tagged commit only if it belongs to `main`'s history.

Before creating a Release, confirm CI passed for its target commit. Create the release from the reviewed `main` commit. No image is published merely by merging a PR.

## Image tags and integrity

Images use version tags, for example:

```sh
docker pull ghcr.io/ismailkqqnalq-dev/careertracker:v0.1.0
```

The workflow does not create or update a `latest` tag. It refuses to overwrite an existing versioned registry tag. GHCR tags are still not a substitute for immutable references: deploy by digest when you need content identity, and never reuse a release tag.

Buildx publishes an SBOM and provenance attestations. The workflow reports the pushed digest and audits that exact digest for prohibited local data, non-root runtime, fail-closed startup without `JWT_SECRET_KEY`, and credential-like strings in Docker history. Trivy scans the candidate before publishing and fails on HIGH or CRITICAL OS/library findings. This threshold may block a release because of upstream base-image or dependency advisories; fix the image or review a narrowly scoped exception rather than disabling the scan.

The publisher uses a job-scoped `GITHUB_TOKEN`: `contents: read` and `packages: write` only for publishing. Actions in the publish workflow are pinned to full commit SHAs. No personal token or Docker Hub account is needed.

GHCR package visibility is controlled separately from this workflow. Check the package settings; publishing does not make the package public.

## Runtime

This is the backend image. It does not bundle the frontend or optional OCR engine. OCR requests return the documented unavailable error without the OCR extra. Supply `DATABASE_URL` and a valid `JWT_SECRET_KEY` through your deployment's secret mechanism; never bake them into an image. Generate a key locally with:

```sh
python -c "import secrets; print(secrets.token_hex(32))"
```

Set `APP_ENV=production`. Registration is disabled unless `APP_ENV=development` is explicitly set or `REGISTRATION_ENABLED=true` is supplied. Keep registration disabled for a deployed instance unless open registration is intentional. Apply database migrations deliberately before serving traffic. Publishing does not deploy a server.

## v0.1.0 verification

The published v0.1.0 artifact was tested by digest:

```
ghcr.io/ismailkqqnalq-dev/careertracker@sha256:a2d887dfcbab46f30e253c1ca7d69573940228c59ea67cc9ad28131b930fe4b2
```

Pulling by tag requires registry authentication while the package is private. Use a version tag for convenience or the digest for exact identity.

### API response security headers

Backend responses handled by the middleware include `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, and `Cache-Control: no-store`.
This covers normal responses and handled errors, including body-size rejections.
Unhandled server errors produced outside the user middleware need equivalent headers
at the reverse proxy. The frontend is served separately and requires its own header
configuration. HTTPS/HSTS, frontend CSP, proxy host restrictions, encrypted backups,
and restore drills remain deployment tasks; these headers do not establish production readiness.
