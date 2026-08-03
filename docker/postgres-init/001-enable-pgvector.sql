-- Runs once, automatically, on first container start against an empty data
-- directory (the official postgres image's own convention for anything
-- mounted at /docker-entrypoint-initdb.d/) — as POSTGRES_USER, which is the
-- bootstrap superuser-equivalent role in a fresh container, so this has the
-- privilege the app's own runtime connection doesn't need and shouldn't
-- have. See docs/DATABASE.md §8's Phase 6 note for why this is a separate,
-- one-time step rather than something a regular migration can do.
CREATE EXTENSION IF NOT EXISTS vector;
