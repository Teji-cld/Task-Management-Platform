# Task Management Platform

A small task manager: create, edit, complete and delete tasks.

This repository contains **application code only**. There are no Dockerfiles, Compose files, or Nginx configuration here on purpose. Writing those is the exercise.

| Part | Technology |
|---|---|
| Frontend | React 18 + Vite |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL (via SQLAlchemy 2.0 and psycopg 3) |
| Cache | Redis (caches `GET /api/tasks`) |

## Architecture

```
 Browser
    |   GET /            -> static files (the React app)
    |   GET /api/tasks   -> API calls (relative URL, same origin)
    v
 Web server / dev proxy
    |   /api/*  is forwarded to the backend
    v
 FastAPI backend (port 8000)
    |-- reads/writes tasks ------> PostgreSQL (port 5432)   <- the source of truth
    `-- caches the task list ----> Redis      (port 6379)   <- optional speed-up
```

- In **development**, Vite's dev server (port 5173) plays the "web server / dev proxy" role.
- In **production**, something else must do it: it serves the built files from `frontend/dist/` and forwards `/api` to the backend. That something is part of the deployment work you will write yourself.

## Project layout

```
task-management-platform/
├── README.md
├── .gitignore
├── backend/
│   ├── requirements.txt          runtime dependencies
│   ├── requirements-dev.txt      runtime + test dependencies
│   ├── .env.example              placeholder settings (copy to .env)
│   ├── pytest.ini                tells pytest where tests are
│   ├── app/
│   │   ├── main.py               FastAPI app and all routes
│   │   ├── config.py             reads environment variables
│   │   ├── database.py           engine, sessions, table creation
│   │   ├── models.py             the `tasks` table
│   │   ├── schemas.py            request/response validation
│   │   └── cache.py              Redis caching helpers
│   └── tests/
│       ├── conftest.py           shared test setup
│       ├── test_health.py        /health and docs
│       ├── test_tasks.py         CRUD, validation, error responses
│       ├── test_cache.py         cache hit/miss/invalidate, Redis outage
│       └── test_external_services.py   needs real PostgreSQL + Redis (skipped by default)
└── frontend/
    ├── package.json
    ├── vite.config.js            dev proxy for /api
    ├── index.html
    └── src/
        ├── main.jsx              entry point
        ├── App.jsx               page, state, loading/empty/error states
        ├── api.js                every HTTP call to the backend
        ├── styles.css
        └── components/
            ├── TaskForm.jsx      "add task" form
            └── TaskItem.jsx      one task row (toggle, edit, delete)
```

## How the pieces work together

### Frontend to backend

`frontend/src/api.js` calls **relative** URLs such as `/api/tasks`. It never contains a hostname or port. The browser sends the request to whichever server delivered the page, and that server must pass `/api` requests to the backend.

- Development: `vite.config.js` proxies `/api` to the backend (default `http://127.0.0.1:8000`).
- Because the browser only ever talks to one origin, **no CORS configuration is needed**.

### PostgreSQL

All tasks live in a table called `tasks`. Every create, update and delete goes to PostgreSQL, and every list request that is not served from the cache reads from it.

**How the table gets created:** when the backend starts, `init_db()` in `backend/app/database.py` runs SQLAlchemy's `Base.metadata.create_all()`. It compares the models in `models.py` with the database and creates any table that is missing. Running it again changes nothing. If PostgreSQL is not reachable yet, the backend retries (`DB_CONNECT_RETRIES` times, `DB_CONNECT_RETRY_DELAY` seconds apart) and then exits with an error. This approach is fine for learning. Real projects use migration tools (such as Alembic) so they can change tables safely later.

Each request gets its own database session. Writes are committed explicitly, and a failed write is rolled back. Database failures return a clean JSON error (`503` if the database is unreachable, `500` for other database errors).

### Redis

Only `GET /api/tasks` is cached, under the key `tasks:list`, and it expires after `CACHE_TTL_SECONDS`.

- **Hit:** the list comes from Redis, the response header says `X-Cache: HIT`.
- **Miss:** the list comes from PostgreSQL, is stored in Redis, header says `X-Cache: MISS`.
- **Invalidation:** creating, updating or deleting a task deletes `tasks:list`, so the next list request is fresh.
- **If Redis is down or disabled:** the error is logged and the API reads from PostgreSQL as if nothing was cached. Nothing breaks. Set `REDIS_ENABLED=false` to turn caching off entirely.

## Environment variables

All backend settings come from environment variables. For local runs you can put them in `backend/.env` (copied from `.env.example`). Real environment variables always take priority over `.env`.

| Variable | Default | Meaning |
|---|---|---|
| `POSTGRES_PASSWORD` | none, **required** | Password of the database user. The backend refuses to start without it. |
| `POSTGRES_USER` | `postgres` | Database user name. |
| `POSTGRES_DB` | `tasks` | Name of the database to use. It must already exist. |
| `POSTGRES_HOST` | `localhost` | Host name of the PostgreSQL server. |
| `POSTGRES_PORT` | `5432` | PostgreSQL port. |
| `DATABASE_URL` | unset | Full SQLAlchemy URL. If set, it replaces all `POSTGRES_*` variables. The tests use it with SQLite. |
| `REDIS_ENABLED` | `true` | Set to `false` to disable caching. |
| `REDIS_HOST` | `localhost` | Host name of the Redis server. |
| `REDIS_PORT` | `6379` | Redis port. |
| `REDIS_DB` | `0` | Redis database number. |
| `REDIS_PASSWORD` | empty | Redis password, if your Redis requires one. |
| `REDIS_SOCKET_TIMEOUT` | `1.0` | Seconds to wait for Redis before giving up on a request. |
| `CACHE_TTL_SECONDS` | `60` | How long the cached task list lives. Must be at least 1. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. |
| `DB_CONNECT_RETRIES` | `10` | Startup attempts to reach PostgreSQL. |
| `DB_CONNECT_RETRY_DELAY` | `2.0` | Seconds between those attempts. |

Frontend: there are no runtime variables. One optional development-only setting exists:

| Variable | Default | Meaning |
|---|---|---|
| `DEV_PROXY_TARGET` | `http://127.0.0.1:8000` | Where the Vite dev server forwards `/api`. Read only by `vite.config.js`. It never ends up in the built JavaScript. |

## Run it locally without Docker

You need: **Python 3.12**, **Node.js 20 or newer**, a **PostgreSQL** server, and (optionally) a **Redis** server.

### 1. PostgreSQL and Redis

On Ubuntu or Debian:

```bash
sudo apt update
sudo apt install -y postgresql redis-server

sudo -u postgres psql -c "CREATE USER tasks_user WITH PASSWORD 'choose-a-password';"
sudo -u postgres psql -c "CREATE DATABASE tasks OWNER tasks_user;"

redis-cli ping        # should print PONG
```

If you don't want Redis for now, skip it and set `REDIS_ENABLED=false` in step 2.

### 2. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate            # Git Bash on Windows: source .venv/Scripts/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set POSTGRES_PASSWORD to the password from step 1

uvicorn app.main:app --reload --port 8000
```

Check it:

```bash
curl http://localhost:8000/health
```

Interactive API documentation: <http://localhost:8000/docs> (Swagger UI) and <http://localhost:8000/redoc>.

### 3. Frontend (in a second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

Other commands: `npm run build` creates the static site in `frontend/dist/`, and `npm run preview` serves that build on port 4173 (with the same `/api` proxy).

> **Working inside a VM or container?** A server that listens on `localhost` can't be reached from outside. Start the servers on all interfaces: `uvicorn app.main:app --host 0.0.0.0 --port 8000` and `npm run dev -- --host`.

## API reference

Base URL while developing: `http://localhost:8000`. Task fields:

| Field | Type | Rules |
|---|---|---|
| `id` | integer | Assigned by the server. |
| `title` | string | Required, 1 to 200 characters after trimming spaces. |
| `description` | string or null | Optional, up to 2000 characters. Blank becomes `null`. |
| `completed` | boolean | Defaults to `false` on create. **Required on update.** |
| `created_at`, `updated_at` | timestamp | Set by the server. |

### `GET /health`

Returns `200` when PostgreSQL answers, `503` when it does not. Redis being down does not cause a `503`.

```bash
curl http://localhost:8000/health
```
```json
{"status": "ok", "database": "up", "redis": "up"}
```

`redis` is `up`, `down` or `disabled`. When the database is unreachable: `{"status": "unavailable", "database": "down", "redis": "up"}` with status `503`.

### `GET /api/tasks`

Lists all tasks, newest first. Status `200`. The `X-Cache` header is `HIT` or `MISS`.

```bash
curl -i http://localhost:8000/api/tasks
```
```json
[
  {
    "id": 2,
    "title": "Set up Compose",
    "description": null,
    "completed": false,
    "created_at": "2026-10-13T09:15:02.114233Z",
    "updated_at": "2026-10-13T09:15:02.114233Z"
  },
  {
    "id": 1,
    "title": "Write the Dockerfile",
    "description": "Start from python:3.12-slim",
    "completed": true,
    "created_at": "2026-10-13T09:10:41.502911Z",
    "updated_at": "2026-10-13T09:12:09.887120Z"
  }
]
```

### `GET /api/tasks/{task_id}`

Returns one task (`200`), `404` if it doesn't exist, `422` if the id is not a positive integer.

```bash
curl http://localhost:8000/api/tasks/1
```
```json
{"detail": "Task not found"}
```
(that last body is what a missing task returns, with status `404`)

### `POST /api/tasks`

Creates a task. Returns `201` with the new task, or `422` if the data is invalid.

```bash
curl -X POST http://localhost:8000/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Write the Dockerfile", "description": "Start from python:3.12-slim"}'
```
```json
{
  "id": 1,
  "title": "Write the Dockerfile",
  "description": "Start from python:3.12-slim",
  "completed": false,
  "created_at": "2026-10-13T09:10:41.502911Z",
  "updated_at": "2026-10-13T09:10:41.502911Z"
}
```

A validation error (`422`) looks like this (exact fields vary a little between library versions):

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "title"],
      "msg": "String should have at least 1 character",
      "input": ""
    }
  ]
}
```

### `PUT /api/tasks/{task_id}`

Replaces a task. Send **all** of `title`, `description` and `completed`. Returns `200` with the updated task, `404` if it doesn't exist, `422` if the data is invalid.

```bash
curl -X PUT http://localhost:8000/api/tasks/1 \
  -H "Content-Type: application/json" \
  -d '{"title": "Write the Dockerfile", "description": null, "completed": true}'
```

### `DELETE /api/tasks/{task_id}`

Deletes a task. Returns `204` with an empty body, or `404` if it doesn't exist.

```bash
curl -i -X DELETE http://localhost:8000/api/tasks/1
```

## Run the tests

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Run `pytest` from inside `backend/`. Useful options: `pytest -v` (list every test), `pytest tests/test_tasks.py` (one file), `pytest -k cache` (tests with "cache" in the name).

**Which tests need PostgreSQL or Redis?**

| Tests | Needs a real PostgreSQL? | Needs a real Redis? |
|---|---|---|
| `test_health.py`, `test_tasks.py` | No. They run the real app against a temporary SQLite file. | No. Redis is switched off. |
| `test_cache.py` | No. | No. They use a small in-memory fake, including a fake that fails like a dead Redis. |
| `test_external_services.py` | Yes | Yes. **Skipped by default.** |

To run everything against real servers, make your environment point at **throwaway** services and run:

```bash
TEST_USE_EXTERNAL_SERVICES=1 pytest
```

In that mode the tests read your normal settings (`backend/.env` or environment variables) and **delete every task** in that database. Never point it at data you care about.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Backend exits: `POSTGRES_PASSWORD is not set` | The variable is missing. Create `backend/.env` from `.env.example`, or export the variable. |
| Log repeats `Database not reachable (attempt ...)` then the backend exits | PostgreSQL isn't running, or `POSTGRES_HOST`/`POSTGRES_PORT` is wrong. Inside a container, `localhost` means the container itself, so use the database service's name. |
| `password authentication failed for user` | `POSTGRES_USER`/`POSTGRES_PASSWORD` don't match the database. Note that the official Postgres image only applies its initial user and password the first time its data directory is created. |
| `database "tasks" does not exist` | Create it (`CREATE DATABASE tasks ...`) or fix `POSTGRES_DB`. The backend creates tables, not databases. |
| `ImportError: no pq wrapper available` | psycopg's binary package isn't installed. Run `pip install -r requirements.txt` again inside the virtual environment. |
| Logs show `Redis read failed` or `/health` says `"redis": "down"` | Redis is unreachable. The API still works (it uses PostgreSQL). Check `REDIS_HOST`/`REDIS_PORT`, or set `REDIS_ENABLED=false`. |
| List is out of date after a change | Normal only for up to `CACHE_TTL_SECONDS` if Redis was down during the change. Otherwise, check the logs for `Redis invalidate failed`. |
| Page says "Can't reach the server" or "The server is unavailable" | The backend isn't running, or `/api` isn't being forwarded to it. In development, check the Vite terminal for proxy errors and `DEV_PROXY_TARGET`. |
| `/api/...` returns `404` from the web server (not JSON) | The web server doesn't forward `/api` to the backend. |
| `/docs` page is blank | Swagger UI loads its JavaScript from a public CDN. It needs internet access from the browser. `/openapi.json` works without it. |
| `ModuleNotFoundError: No module named 'app'` | Run `pytest` and `uvicorn` from inside the `backend/` folder. |
| `Address already in use` | Another program uses port 8000 or 5173. Stop it or pick another port (`--port 8001`). |
| `npm install` or `npm run dev` fails with engine/syntax errors | Node.js is too old. Use Node 20 or newer (`node --version`). |

## What to understand before you containerize

- **Backend:** Python 3.12. Install with `pip install -r requirements.txt`. Start from the `backend/` folder with `uvicorn app.main:app --host 0.0.0.0 --port 8000`. It must listen on `0.0.0.0` inside a container, or nothing outside can reach it.
- **Frontend:** needs Node 20+ **only to build** (`npm install` then `npm run build`). The output, `frontend/dist/`, is plain static files, so running it needs only a web server. The built app has no environment variables.
- **Routing:** the browser calls `/api/...` on the same host as the page. Whatever serves the frontend must forward `/api` to the backend. The backend also serves `/health`, `/docs`, `/redoc` and `/openapi.json` outside `/api`.
- **Service names:** inside a container network, use each service's name as its host name (`POSTGRES_HOST`, `REDIS_HOST`), never `localhost`.
- **PostgreSQL:** the `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` variable names are the same ones the official `postgres` image uses, so one set of values can configure both. The database files need a persistent volume. The backend creates the tables itself, but the database must exist.
- **Redis:** holds only a cache that can be rebuilt, so it needs no volume. The backend runs without it.
- **Startup order:** the backend retries the database connection for about `DB_CONNECT_RETRIES x DB_CONNECT_RETRY_DELAY` seconds, then exits. It does not wait for Redis.
- **Health check:** `GET /health` returns `200` or `503`. Minimal images may not contain `curl`.
- **Secrets:** never put `backend/.env` into an image. Pass real values at run time. Keep `.env`, `node_modules`, `.venv` and `__pycache__` out of images with a `.dockerignore`.
- **Single worker:** the table creation at startup is not designed for several backend processes starting at the same moment. Run one worker for now.
- **Lock file:** `frontend/package-lock.json` does not exist until you run `npm install` once. Commit it, then `npm ci` gives reproducible builds. Do the same for the backend with `pip freeze`.
