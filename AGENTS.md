# Project workflow

Read [docs/SRS.md](docs/SRS.md), [docs/UI_OVERHAUL.md](docs/UI_OVERHAUL.md), and the selected ticket before changing the pilot. Requirements describe intended behavior; do not claim it already exists.

Use [features.md](features.md) and [bugs.md](bugs.md) for ticket status, [docs/GROOMING.md](docs/GROOMING.md) for dependencies/readiness, [VERIFICATION.md](VERIFICATION.md) for the verification procedure, and [README.md](README.md#the-cycle-file-contract) for the cycle-file contract. Keep changelog history append-only and preserve all ticket IDs.

New features/bugs use epoch-second IDs and append to the Open section. Scope before coding. On verified delivery, add Implementation/Fix and Docs notes and set the pending-migration status. Only full V&V migrates completed tickets to [CHANGELOG.md](CHANGELOG.md). Local reports/backups belong in ignored `.vv/`.

Keep the existing personal instruction mechanism outside committed project files. Do not import historical scraped content into private pilot storage, bypass provider policy gates, or describe seeded/liveness checks as proof of live research. Production changes require separate authorization.
