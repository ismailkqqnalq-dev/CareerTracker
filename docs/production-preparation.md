# HTTPS and backup preparation

This is a deployment template, not evidence of a deployed or production-certified service.
Use `deploy/compose.production.yml` alone, NOT as an override of the development Compose.
Only Caddy publishes ports. Backend/database have no host ports and no source-code mount.

## Operator setup (Linux server)

1. Choose an updated Linux host, firewall inbound traffic to SSH (restricted source IP), 80 and 443. Configure a DNS hostname pointing at it. Hosting, DNS, certificates and firewall have not been configured by this PR.
2. Build `frontend/dist` with `npm ci && npm run build` in `frontend/` from the same reviewed commit as the backend image. Copy the build and `deploy/` to the host without credentials, databases or development files.
3. Create a private deployment environment file OUTSIDE the checkout (`chmod 600 /secure/careertracker.env`). Set `SITE_DOMAIN` to a hostname only (no scheme/path), `CADDY_IMAGE` to an audited Caddy 2 image digest, `POSTGRES_IMAGE` to an audited PostgreSQL 16 image digest and `APP_IMAGE` to the reviewed backend image digest. Choose current, scanned images; the CI smoke uses moving major tags only for tooling checks.
4. Set `POSTGRES_PASSWORD`, `JWT_SECRET_KEY` (at least 32 random bytes) and `DATABASE_URL` to `postgresql://careertracker:<URL-encoded-password>@db:5432/careertracker`. Do not paste secrets into Git, chat, shell history or logs. The database URL and database password must agree. Registration is deliberately closed.
5. Ensure subnet `172.30.40.0/24` does not overlap the host/VPN. If changed, update both proxy IP and `TRUSTED_PROXY_IPS`. Only Caddy's fixed IP is trusted. Uvicorn proxy interpretation is disabled so the application validates forwarded IPs itself. One worker preserves the current process-local limits. No CDN/proxy is assumed ahead of Caddy.
6. Run these commands from the repository root (never print expanded Compose configuration containing secrets):

```sh
docker compose --env-file /secure/careertracker.env -f deploy/compose.production.yml config --quiet
docker compose --env-file /secure/careertracker.env -f deploy/compose.production.yml up -d db
docker compose --env-file /secure/careertracker.env -f deploy/compose.production.yml run --rm app python3 -m alembic upgrade head
docker compose --env-file /secure/careertracker.env -f deploy/compose.production.yml up -d app proxy
```

Back up an existing database BEFORE migrations. No automatic migrations run at startup.
The template uses its own named database volume; it does not migrate a local SQLite database.
Never use `down -v` on a deployment containing data.

Caddy terminates HTTPS, redirects HTTP, persists certificates in `caddy_data`, strips `/api`
when proxying and serves the built SPA on the same origin. Public API docs are blocked.
Keep both Caddy volumes. Backend access logs are disabled; Caddy access logging is not enabled.
Runtime error logs still need restricted access and a retention policy.
HSTS lasts one year without preload/subdomain opt-in; enable this host only when HTTPS is durable.
Frontend CSP permits inline styles because current React components use them, but not inline scripts.
Google Fonts is permitted by CSP and sends requests to Google; self-host fonts for a fully local asset policy.
The backend image does not include optional OCR/semantic dependencies; this template does not add them.

## SQLite backup and safe restore (local use)

The standalone tool never loads `.env`, requires explicit paths, uses the SQLite backup API
(including committed WAL data), checks integrity and foreign keys, and refuses to overwrite a destination.
It publishes the output only after validation. Destination directory must already exist.
An interrupted run may leave a `.snapshot-*` temporary file; protect the backup directory.

```powershell
python scripts/sqlite_snapshot.py --source C:\path\source.db --destination C:\private-backups\snapshot.db
python scripts/sqlite_snapshot.py --source C:\private-backups\snapshot.db --destination C:\private-restore\restored.db
```

Restore into a new file, then stop the backend and validate that copy before explicitly changing
DATABASE_URL. Never restore over a running database. Restrict directory ACLs on Windows;
on Linux use a private directory and `umask 077`. Output is NOT encrypted by this script.

## PostgreSQL encrypted backups (Linux host)

Use the same PostgreSQL major-version tools as the server. `pg_dump -Fc` provides a consistent
logical snapshot. Install `age` separately and keep its decryption identity offline/outside the host.
The example below uses a public recipient, not a secret. Set `AGE_RECIPIENT` from the backup key's
public recipient and keep `/secure/backups` private. Run from the repository root.

```bash
set -euo pipefail
umask 077
mkdir -p /secure/backups
backup_file="/secure/backups/careertracker-$(date -u +%Y%m%dT%H%M%SZ).dump.age"
test ! -e "$backup_file"
docker compose --env-file /secure/careertracker.env -f deploy/compose.production.yml exec -T db pg_dump -U careertracker -d careertracker -Fc --no-owner --no-acl | age -r "${AGE_RECIPIENT:?Set backup public recipient}" > "$backup_file.partial"
mv -n "$backup_file.partial" "$backup_file"
```

A failed pipeline must alert the operator; never promote its partial file. Use a job lock if automated.
Copy successful encrypted backups off-host using restricted credentials. Proposed schedule: daily,
7 daily + 4 weekly + 3 monthly copies. This is a policy proposal, not an installed scheduler.
Do not delete older backups until an off-host copy and periodic restore have succeeded.
Monitor last successful backup age (alert after 26 hours), disk usage and TLS expiry.

Restore only a trusted archive into a NEW isolated database, never directly over production:

```bash
set -euo pipefail
umask 077
age -d -i /secure/offline-key.txt /secure/backups/snapshot.dump.age > /secure/restore.dump
# Use a disposable PostgreSQL 16 instance with local restricted credentials:
createdb careertracker_restore_drill
pg_restore --exit-on-error --single-transaction --no-owner --no-acl -d careertracker_restore_drill /secure/restore.dump
```

Check schema revision, row counts, relationships and application login on that isolated copy.
Then remove decrypted staging files according to your disk/encryption policy. Keep JWT secrets and
Caddy keys in a separate encrypted recovery plan; database dumps alone cannot restore the whole service.
The CI drill proves synthetic PostgreSQL data survives dump/restore; it does not prove off-host
storage, encryption key recovery or real account access. Repeat a full restore drill monthly.

## Verification and remaining deployment checks

CI validates Compose syntax, Caddy configuration, actual HTTP routing/CSP/docs blocking and a synthetic
PostgreSQL dump/restore. SQLite tests cover WAL snapshots, restore contents, corrupt sources and
non-overwrite behavior. CI uses disposable containers and no production secrets.
A real DNS certificate, HTTPS browser flow, host firewall, off-host encrypted backup, scheduler,
alerts and recovery-key custody require the selected hosting environment. They are not tested here.
After deployment check registration closed, login, CRM/OCR flows supported by the chosen image,
HTTP-to-HTTPS redirect, security headers and direct backend/database ports unreachable externally.

Official references:
- https://caddyserver.com/docs/automatic-https
- https://caddyserver.com/docs/caddyfile/directives/handle_path
- https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- https://www.postgresql.org/docs/16/app-pgdump.html
- https://www.postgresql.org/docs/16/app-pgrestore.html
