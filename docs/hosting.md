# Hosting without Railway

The web app runs as one Docker service on Render's Free plan. Its durable data
lives in a Neon Free Postgres database, selected with `DATABASE_URL`. The local
development default remains SQLite at `DATABASE_PATH`.

Set these secrets in the host's environment:

- `DATABASE_URL`: the Postgres connection string, with TLS enabled.
- `ANTHROPIC_API_KEY` and `BRAVE_API_KEY`: the existing provider credentials.
- `BASE_URL`: the app's public HTTPS origin, used for canonical URLs and previews.

`render.yaml` declares the free service and `/api/health` probe. The container
honors the host's `PORT`; its default remains 8000 for local development.
Its build includes the required Rust normalization library; the runtime image does
not compile Rust or start another service.
Never put SQLite files, environment files, or credentials in a Docker build context.

## Migrate existing data

1. Take a consistent SQLite backup using SQLite's backup API while the original
   service is running. Copying only the `.db` file can omit committed WAL data.
2. Stop accepting new writes on the old instance for the final cutover snapshot.
3. Set `DATABASE_URL` to a new empty destination and run:

   ```sh
   python -m scripts.import_sqlite /private/path/factchecker.db
   ```

   This initializes the schema, imports videos, claims, and sources atomically,
   verifies every imported row, and updates ID sequences. It refuses to overwrite
   a populated destination. Retain the source backup until the replacement is verified.
4. Start the replacement and verify health, existing videos, channels, and a
   fact-check request. Update any external links before retiring the old origin.

## Free-plan constraints

Render Free sleeps an idle service, so the first request can have a cold start.
Its local filesystem is temporary; hosted data must use Postgres. A sleeping
service cannot promise continuous queue processing: queued jobs resume when the
service wakes. Active requests and their background tasks share one worker.
Neon's Free plan has storage, compute, and transfer quotas. Keep it on Free;
upgrade only through a separate spending decision.

Anthropic's API charges remain separate from hosting. This migration does not
make model inference free.

## Verify locally

```sh
python scripts/build_native.py
pytest tests/unit tests/services tests/integration
TEST_DATABASE_URL=postgresql://... pytest tests/integration
```

The second command runs the same API and storage contracts against isolated
Postgres schemas and removes only those test schemas afterward.

References checked November 3, 2026:
[Render Free](https://render.com/docs/free),
[Neon Free](https://neon.com/pricing).
