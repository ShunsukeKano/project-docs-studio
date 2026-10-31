-- 001_schema.sql
-- Schema for Docs Studio (PostgreSQL). Apply the files in this folder in numeric order.
-- Source of truth for the data model; docs/nextjs-fastapi-architecture.html (section 7) mirrors it.

-- ---------------------------------------------------------------------------
-- articles: the draft and the publication state of one article
-- ---------------------------------------------------------------------------
CREATE TABLE articles (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  slug          TEXT        NOT NULL UNIQUE
                CHECK (char_length(slug) BETWEEN 1 AND 100
                       AND slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  status        TEXT        NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'published', 'unpublished')),

  -- Draft content (editable). Never shown to the public side.
  draft_title   TEXT        NOT NULL
                CHECK (char_length(btrim(draft_title)) BETWEEN 1 AND 200),
  draft_body    TEXT        NOT NULL DEFAULT ''
                CHECK (char_length(draft_body) <= 100000),
  draft_tags    TEXT[]      NOT NULL DEFAULT '{}'
                CHECK (cardinality(draft_tags) <= 10),

  -- Optimistic concurrency: bumped by an edit, a Restore, and a Publish that creates a snapshot.
  draft_version INTEGER     NOT NULL DEFAULT 1 CHECK (draft_version >= 1),

  -- Per-article counter used to number snapshots. It never goes down, so numbers are never reused.
  last_version_number INTEGER NOT NULL DEFAULT 0 CHECK (last_version_number >= 0),

  -- Publication state
  current_published_version_id BIGINT,           -- the protected (live) version; kept after Unpublish
  published_at  TIMESTAMPTZ,                      -- first publication time; never changes once set

  created_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

  -- A never-published article has no pointer and no published_at; every other state has both.
  CONSTRAINT articles_publish_consistency CHECK (
    (status = 'draft'
       AND current_published_version_id IS NULL AND published_at IS NULL)
    OR
    (status IN ('published', 'unpublished')
       AND current_published_version_id IS NOT NULL AND published_at IS NOT NULL)
  )
);

-- ---------------------------------------------------------------------------
-- article_versions: immutable published snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE article_versions (
  id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  article_id     BIGINT      NOT NULL REFERENCES articles (id) ON DELETE RESTRICT,
  version_number INTEGER     NOT NULL CHECK (version_number > 0),
  title          TEXT        NOT NULL,
  body           TEXT        NOT NULL,
  tags           TEXT[]      NOT NULL DEFAULT '{}' CHECK (cardinality(tags) <= 10),
  created_at     TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
  UNIQUE (article_id, version_number),
  UNIQUE (article_id, id)              -- target of the composite foreign key below
);

-- An article can only point at one of its own versions, and a referenced version cannot be deleted.
-- With a NULL pointer (never published) the foreign key is not checked (MATCH SIMPLE).
ALTER TABLE articles
  ADD CONSTRAINT articles_current_version_fk
  FOREIGN KEY (id, current_published_version_id)
  REFERENCES article_versions (article_id, id) ON DELETE RESTRICT;

-- ---------------------------------------------------------------------------
-- Guards
-- ---------------------------------------------------------------------------

-- Snapshots are immutable: reject every UPDATE (DELETE stays allowed; the foreign key protects the live one).
CREATE FUNCTION forbid_version_update() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
  RAISE EXCEPTION 'article_versions is immutable';
END $$;

CREATE TRIGGER article_versions_immutable
  BEFORE UPDATE ON article_versions
  FOR EACH ROW EXECUTE FUNCTION forbid_version_update();

-- TRUNCATE bypasses row triggers, so guard it separately.
-- The only exception is the test suite, which resets the data between tests inside a transaction
-- that first runs: SET LOCAL docs.allow_reset = 'on'. The application never sets it, and the
-- application role has no TRUNCATE privilege.
CREATE FUNCTION forbid_version_truncate() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog AS $$
BEGIN
  IF current_setting('docs.allow_reset', true) = 'on' THEN
    RETURN NULL;
  END IF;
  RAISE EXCEPTION 'article_versions cannot be truncated';
END $$;

CREATE TRIGGER article_versions_no_truncate
  BEFORE TRUNCATE ON article_versions
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_version_truncate();

-- Once published, an article never goes back to "never published", keeps its published_at,
-- and its pointer only moves forward. The slug never changes. updated_at is maintained here.
CREATE FUNCTION articles_guard() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
BEGIN
  IF NEW.slug IS DISTINCT FROM OLD.slug THEN
    RAISE EXCEPTION 'slug cannot be changed';
  END IF;

  IF OLD.current_published_version_id IS NOT NULL THEN
    IF NEW.current_published_version_id IS NULL OR NEW.status = 'draft' THEN
      RAISE EXCEPTION 'a published article cannot return to draft';
    END IF;
    IF NEW.published_at IS DISTINCT FROM OLD.published_at THEN
      RAISE EXCEPTION 'published_at cannot change once set';
    END IF;
    IF NEW.current_published_version_id IS DISTINCT FROM OLD.current_published_version_id
       AND (SELECT version_number FROM article_versions WHERE id = NEW.current_published_version_id)
        <= (SELECT version_number FROM article_versions WHERE id = OLD.current_published_version_id) THEN
      RAISE EXCEPTION 'the live version can only move forward';
    END IF;
  END IF;

  NEW.updated_at := clock_timestamp();
  RETURN NEW;
END $$;

CREATE TRIGGER articles_guard_trg
  BEFORE UPDATE ON articles
  FOR EACH ROW EXECUTE FUNCTION articles_guard();

-- ---------------------------------------------------------------------------
-- Indexes
-- (article_versions needs no extra index: UNIQUE (article_id, version_number) already serves it)
-- ---------------------------------------------------------------------------
CREATE INDEX articles_public_idx
  ON articles (published_at DESC, id DESC) WHERE status = 'published';
CREATE INDEX articles_writer_list_idx
  ON articles (updated_at DESC, id DESC);

-- ---------------------------------------------------------------------------
-- Privileges (adjust the role names to your environment; run as the owner / migration role)
-- ---------------------------------------------------------------------------
-- REVOKE UPDATE, TRUNCATE ON article_versions FROM app_role;
-- GRANT SELECT, INSERT, DELETE ON article_versions TO app_role;
-- GRANT SELECT, INSERT, UPDATE ON articles TO app_role;
