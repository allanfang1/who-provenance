# DevContainer: Python + PostgreSQL + pgaudit

A devcontainer setup with a Python app container and a PostgreSQL database with pgaudit logging, where logs are accessible from both containers.

---

## Structure

```
.devcontainer/
├── docker-compose.yml
├── Dockerfile                  # app container
├── Dockerfile.db               # postgres container
├── fix-perms-entrypoint.sh     # fixes /logs permissions before postgres starts
└── 01-init-pgaudit.sql         # installs pgaudit extension on first run
```

---

## How It Works

### Two containers, one shared log volume

The `app` and `db` containers share a named volume mounted at `/logs`. Postgres writes audit logs there; the app reads them.

The postgres data directory (`$PGDATA`) is kept on a **separate** volume and is never mounted into the app container — postgres is strict about who can access it and sharing it causes permission errors.

### pgaudit setup

pgaudit requires two things:
1. The shared library loaded at startup — set via `shared_preload_libraries=pgaudit` in the compose command
2. The extension installed in the database — done via `01-init-pgaudit.sql` which runs once after `initdb` on first startup

### Log directory permissions

Docker creates named volumes owned by `root`. Since postgres runs as the `postgres` user it can't write to `/logs` without a permission fix. `fix-perms-entrypoint.sh` runs as `root` before postgres starts, sets the correct ownership and permissions, then hands off to the normal postgres entrypoint.

Logs are written as `.csv` files (`log_destination=csvlog`) so they can be programmatically parsed. The app container can read them at `/logs/`.

---

## Files

### docker-compose.yml

### Dockerfile (app)

### fix-perms-entrypoint.sh

Runs as `root` before postgres starts. Fixes ownership and permissions on `/logs` (`0755` = postgres can write, all others can read), then delegates to the standard postgres entrypoint.

### 01-init-pgaudit.sql

Runs once after `initdb` completes on first startup. Files in `/docker-entrypoint-initdb.d/` are executed in alphabetical order.

---

## Startup Sequence

1. `fix-perms-entrypoint.sh` runs as `root`, fixes `/logs` permissions
2. postgres runs `initdb` to initialize `$PGDATA`
3. `01-init-pgaudit.sql` installs the pgaudit extension
4. postgres starts accepting connections with pgaudit active
5. Audit logs are written as `.csv` files to `/logs`
6. App container reads logs from `/logs` via the shared volume

---

## Accessing Logs

From the app container:
```bash
ls /logs
cat /logs/postgresql-YYYY-MM-DD_HHMMSS.csv
```

From outside (host machine):
```bash
docker exec -it <db_container> ls /logs
```

---

## Troubleshooting

### Verify pgaudit is loaded and configured
```sql
SHOW shared_preload_libraries;   -- should contain pgaudit
SHOW pgaudit.log;                -- should show WRITE, ROLE, DDL
SELECT * FROM pg_extension WHERE extname = 'pgaudit';  -- should return a row
```

### Verify logging is working
```sql
SHOW logging_collector;   -- should be on
SHOW log_destination;     -- should be csvlog
SHOW log_directory;       -- should be /logs
```

### Trigger an auditable event and check for output
```sql
CREATE TABLE test_audit (id int);
DROP TABLE test_audit;
```
```bash
ls /logs                  -- should show .csv files
grep -i pgaudit /logs/postgresql-*.csv
```

### Check the logger process is running
```bash
docker exec -it <db_container> ps aux | grep postgres
# should show a separate "postgres: logger" process
```

### Permissions issue on /logs
```bash
docker exec -u root <db_container> chmod 0755 /logs
```
If this keeps happening on rebuild, check `fix-perms-entrypoint.sh` is copied and executable in `Dockerfile.db`.