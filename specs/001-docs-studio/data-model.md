# Data Model: Docs Studio

Phase 1 output of `/speckit-plan`. The authoritative DDL is `backend/db-automation-apply/001_schema.sql`; this document explains it and ties each rule to the spec. Entities come from [spec.md](./spec.md) (Key Entities).

## Entities

### Article (`articles`)

One article: its draft and its publication state live in one row, **but published content never does** (it is in `article_versions`).

| Field | Type | Rules |
|---|---|---|
| `id` | bigint, generated | Primary key. Writer operations address an article by `id`. |
| `slug` | text | Unique. 1 to 100 characters, lowercase letters, digits and single hyphens (`^[a-z0-9]+(-[a-z0-9]+)*$`). Never changes after creation (trigger). Public operations address an article by `slug`. |
| `status` | text | `draft` (never published), `published`, or `unpublished` (taken down). |
| `draft_title` | text | 1 to 200 characters after trimming. |
| `draft_body` | text | At most 100,000 characters; may be empty in a draft. |
| `draft_tags` | text[] | At most 10 items; each 1 to 30 characters, trimmed, lowercased, no duplicates (order kept). The application normalizes; the database caps the count. |
| `draft_version` | integer | Starts at 1, never below 1. The optimistic-concurrency token. Incremented by an edit, by a Restore and by a Publish that creates a snapshot; unchanged by Unpublish, Delete version and an idempotent Publish. |
| `last_version_number` | integer | Starts at 0, never decreases. The counter that numbers snapshots, so a number is never reused. |
| `current_published_version_id` | bigint, nullable | The **protected (live) version**. Kept after Unpublish. Only moves forward. |
| `published_at` | timestamptz, nullable | The first publication time. Set once, never changed. |
| `created_at`, `updated_at` | timestamptz | Statement time (`clock_timestamp()`); `updated_at` is maintained by the guard trigger. |

### Version (`article_versions`)

A permanent, numbered snapshot of the draft at a Publish. It belongs to one article and never changes.

| Field | Type | Rules |
|---|---|---|
| `id` | bigint, generated | Primary key. |
| `article_id` | bigint | Foreign key to `articles(id)`, `ON DELETE RESTRICT`. |
| `version_number` | integer | Greater than 0. Unique per article (`UNIQUE (article_id, version_number)`). Taken from `last_version_number`. |
| `title`, `body`, `tags` | text, text, text[] | Copied from the draft at the Publish. `tags` holds at most 10 items. |
| `created_at` | timestamptz | Statement time. This is the "updated date" shown on the public side for a republished article. |

The snapshot has **no slug** (a Restore never copies one).

### Writer and Reader

Not stored. A **Writer** is whoever presents the configured Basic credentials; a **Reader** is anyone else. There are no accounts and no roles.

## Relationships

- An article has many versions (`article_versions.article_id`).
- An article points at most one of its own versions as live: the composite foreign key `(id, current_published_version_id)` references `article_versions (article_id, id)` with `ON DELETE RESTRICT`. A NULL pointer (never published) skips the check.
- Derived: the **protected version** is the version `current_published_version_id` points to, in every state.

## State and operation matrix

| Operation | From status | To status | Live pointer | `published_at` | `draft_version` | Snapshots | Result |
|---|---|---|---|---|---|---|---|
| Create | — | `draft` | none | none | 1 | none | 201 |
| Edit the draft | any | unchanged | unchanged | unchanged | +1 | unchanged | 200 (409 if stale) |
| Publish, first time | `draft` | `published` | new v1 | set once | +1 | +1 new | 201 |
| Publish, changed draft | `published` / `unpublished` | `published` | new version | kept | +1 | +1 new | 201 |
| Publish, draft equals live | `published` | `published` | unchanged | kept | unchanged | none | 200 |
| Publish, draft equals live | `unpublished` | `published` | unchanged | kept | unchanged | none | 200 |
| Unpublish | `published` | `unpublished` | kept | kept | unchanged | none | 200 |
| Unpublish | `draft` / `unpublished` | none | none | none | none | none | 409 `not_published` |
| Restore vN | any | unchanged | unchanged | unchanged | +1 | none (all rows identical) | 200 (404 / 409) |
| Delete a version | any | unchanged | unchanged | unchanged | unchanged | −1 (not the protected one) | 204 |
| Delete the protected version | `published` / `unpublished` | none | none | none | none | none | 409 `version_is_live` |

```text
            Publish (first)               Unpublish
   draft ──────────────────▶ published ─────────────▶ unpublished
                              ▲   │  ▲                     │
                              │   └──┘ Publish             │
                              │   (new version, or          │
                              │    no-op if unchanged)      │
                              └─────────────────────────────┘
                                   Publish (republish)
   Edit and Restore never change the status; they change only the draft.
```

A published article never returns to `draft`; once `current_published_version_id` is set, it stays set.

## Validation rules (from the spec)

| Rule | Where it is enforced |
|---|---|
| Title 1 to 200 characters, not only whitespace (FR-003) | Application (422 `validation_error`); database CHECK |
| Slug format and length (FR-003) | Application; database CHECK |
| At most 10 tags, each 1 to 30 characters, normalized (FR-003) | Application normalizes and validates; database caps the count |
| Body at most 100,000 characters; empty allowed in a draft (FR-003) | Application; database CHECK |
| Publish needs a non-empty title and body (FR-008) | Application (422 `empty_content`) |
| The slug never changes (FR-002) | Application (PATCH accepts no slug); `articles_guard` trigger |
| The writer's list `status` filter must be a known value (FR-004) | Application (422) |
| List `limit` at most 100 (FR-004, FR-022) | Application |

## Invariants and where each is enforced

| Invariant | Application | Database |
|---|---|---|
| INV-001 Snapshots never change | No update path exists | `article_versions_immutable` trigger rejects UPDATE; `article_versions_no_truncate` trigger rejects TRUNCATE (except under the test-only `docs.allow_reset` setting); `REVOKE UPDATE, TRUNCATE` from the application role |
| INV-002 Publish is atomic | One transaction under the row lock; statement-time timestamps | `articles_publish_consistency` CHECK and the composite foreign key |
| INV-003 The protected version cannot be deleted | Delete takes the row lock and checks the pointer (409) | Composite foreign key `ON DELETE RESTRICT` |
| INV-004 Restore never harms history | One `UPDATE` of the draft columns and `draft_version` | (Tests compare every row of `article_versions` before and after) |
| INV-005 Conflicting edits are detected | `WHERE draft_version = :expected`; the same comparison under the lock for Publish | — |
| INV-006 History survives unpublishing | Unpublish only updates `status` | CHECK and `articles_guard` keep the pointer and `published_at`; no return to `draft`; the pointer never moves back |

## Indexes

- `articles_public_idx` on `(published_at DESC, id DESC) WHERE status = 'published'`: the public list.
- `articles_writer_list_idx` on `(updated_at DESC, id DESC)`: the writer's list.
- `article_versions` needs no extra index: `UNIQUE (article_id, version_number)` serves the history list.

## Public projections (what a reader may see)

| Projection | Fields |
|---|---|
| Public list item | `slug`, `title`, `tags`, `published_at`, and `updated_at` (the live snapshot's `created_at`) only when the live `version_number` is 2 or more |
| Public article | `slug`, `title`, `tags`, `body`, `published_at`, and the live snapshot's `created_at` |

Both are read from the live snapshot with **one** join, so the title and body always come from the same version. They never include `draft_*`, `draft_version`, `articles.updated_at`, `status` or an internal id.
