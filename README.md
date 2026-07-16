# Romance Agent

## Docker Compose development stack

Docker Desktop or another Docker Engine with Compose v2 is the only host
runtime required for the containerized workflow.

Start the frontend, backend, PostgreSQL, and Neo4j together from the repository
root:

```sh
docker compose up --build
```

Run in the background with `-d`:

```sh
docker compose up --build -d
docker compose ps
```

### Local endpoints

| Service | Address |
| --- | --- |
| Frontend | <http://127.0.0.1:5173> |
| Backend health | <http://127.0.0.1:8000/health> |
| PostgreSQL | `postgresql://romance_agent:romance_agent_dev@127.0.0.1:5432/romance_agent` |
| Neo4j Browser | <http://127.0.0.1:7474> |
| Neo4j Bolt | `bolt://127.0.0.1:7687` |

Neo4j uses username `neo4j` and the development password
`romance_agent_dev`.

The frontend uses its existing MSW scenarios by default. The backend runs at
the same time and can be checked directly through `/health`. PostgreSQL and
Neo4j are prepared for later integration; the backend does not use either
database yet.

### Configuration

The stack works without a `.env` file. To override ports, mock behavior, or
development credentials:

```sh
cp .env.example .env
```

The real `.env` file is ignored by Git. Database initialization credentials are
applied only when their data volumes are first created.

### Development operations

Frontend and backend source directories are mounted into their containers.
Vite hot module replacement and Uvicorn reload apply source edits without an
image rebuild.

```sh
docker compose logs -f frontend backend
docker compose exec backend uv run --no-sync pytest
docker compose exec frontend pnpm test
```

Stop containers while preserving all data:

```sh
docker compose down
```

Delete containers and all Compose-owned PostgreSQL, Neo4j, backend file, and
frontend dependency volumes:

```sh
docker compose down -v
```

`down -v` is destructive. Use it only when the local stack data should be
reinitialized.
