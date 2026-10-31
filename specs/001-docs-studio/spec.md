# Feature Specification: Docs Studio

**Feature Branch**: none (no git branch is created; the work lives in `specs/001-docs-studio`)

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description: "A small content management service for internal writers (an API plus a minimal UI) and a public documentation site where only published articles can be read. Source of truth: `docs/requirements.md` (Japanese twin: `docs/ja/requirements.md`)."

## User Scenarios & Testing *(mandatory)*

Docs Studio has two audiences. **Writers** (a small internal team) create and edit articles, publish them, take them down, and manage version history. **Readers** (anyone on the internet, not signed in) can read published articles only.

The idea that shapes everything: a writer can edit freely without ever changing what readers see, and what readers see is always a frozen, reviewable snapshot of what was last published. Every story below follows from that.

### User Story 1 - Create and edit a draft (Priority: P1)

A writer creates an article by entering a title, a slug (the article's address), a body written in Markdown and some tags. The writer can keep editing the draft as often as needed and can see a rendered preview of the Markdown while editing. A writer can also list all articles, in any state, to find the one to work on.

**Why this priority**: Nothing else can happen without drafts. Editing must be safe: a draft is private working copy and never affects readers.

**Independent Test**: Create an article, edit it twice, and open the writer's article list. The article shows its latest draft values, and the public site shows nothing for it.

**Acceptance Scenarios**:

1. **Given** no article exists, **When** a writer creates one with a valid title, slug, body and tags, **Then** the article exists as a never-published draft and appears in the writer's list.
2. **Given** a draft, **When** the writer edits its title, body or tags, **Then** the new values are saved and the draft's version number goes up by one.
3. **Given** a slug that is already taken, **When** a writer creates another article with it, **Then** the new article is created with a number appended to the slug (for example `-2`), and the writer is shown the slug that was actually stored.
4. **Given** invalid input (an empty title, a malformed slug, too many tags, or a body that is too long), **When** the writer saves it, **Then** it is rejected with a clear message and nothing is changed.
5. **Given** a stored article, **When** the writer tries to change its slug, **Then** the change is refused; a slug never changes after creation.

---

### User Story 2 - Publish a draft as an immutable snapshot (Priority: P1)

A writer publishes the current draft. The system freezes the draft's title, body and tags into a new, numbered, permanent snapshot, marks the article as published, and makes that snapshot the one readers see. The first time an article is published, its publication date is recorded; republishing never changes that date.

**Why this priority**: This is the heart of the product and the most heavily assessed behaviour. It must be all-or-nothing and must never disturb what was already published.

**Independent Test**: Publish a draft and check that the article is live, has snapshot number 1, and records the publication date. Edit the draft, publish again, and check that there is a snapshot number 2, the live snapshot is now number 2, and the publication date is unchanged.

**Acceptance Scenarios**:

1. **Given** a never-published draft the writer is looking at, **When** the writer publishes it, **Then** a new snapshot number 1 holds the draft's title, body and tags, the article becomes published, the live snapshot is number 1, and the publication date is set.
2. **Given** a published article whose draft has since been edited, **When** the writer publishes again, **Then** a new snapshot with the next number is created, it becomes the live snapshot, and the original publication date is kept.
3. **Given** a publish that fails part-way for any reason (including a crash), **When** the system recovers, **Then** nothing changed: no new snapshot exists, and the status, live snapshot, publication date and draft version are exactly as before.
4. **Given** two publish requests arrive at the same moment from the same screen state, **When** they are processed, **Then** exactly one succeeds and the other is rejected as out of date; there are never two snapshots from one screen state, no server error, and snapshot numbers stay in unbroken order.
5. **Given** a draft whose title or body is empty, **When** the writer publishes, **Then** the publish is refused with a clear message and nothing is created.
6. **Given** any moment in time, **When** the data is inspected, **Then** none of these states ever exist: published with no live snapshot; published but pointing at an old snapshot; not published but a live snapshot is set.

---

### User Story 3 - Readers see only published content (Priority: P1)

A reader opens the public site and sees a list of published articles, showing each title, its tags and its publication date (and an "updated" date when the article has been republished). Opening an article shows the content of its live snapshot. Articles that were never published, articles that were taken down, and addresses that do not exist all look exactly the same to a reader: a plain "not found" response.

**Why this priority**: The whole point of publishing is what readers see, and a leak of draft content would defeat the product.

**Independent Test**: Publish an article, then edit its draft without publishing. The public page still shows the published text. Then check a never-published article, a taken-down article and a made-up address: all return the same "not found".

**Acceptance Scenarios**:

1. **Given** published articles, **When** a reader opens the list, **Then** it shows only published articles, newest publication date first, with title, tags and publication date.
2. **Given** a republished article (its live snapshot is not the first one: its number is 2 or more), **When** a reader opens the list, **Then** the entry also shows an updated date taken from the live snapshot.
3. **Given** a published article whose draft was edited afterwards, **When** a reader opens it, **Then** the reader sees the live snapshot's title, tags and body, never the draft.
4. **Given** a never-published article, a taken-down article, or an address that does not exist or is malformed, **When** a reader requests it, **Then** the response is the same "not found" response with the same body each time, with no error detail and no draft content.
5. **Given** a public response, **When** it is inspected, **Then** it contains only the article's address, title, tags, body (on the detail page), publication date and live snapshot date, and never draft fields, internal numbers or the article's state.
6. **Given** a writer takes an article down, **When** a reader reloads, **Then** the article is gone on that very next request.
7. **Given** there are no published articles, **When** a reader opens the list, **Then** an empty list is shown with a friendly message.

---

### User Story 4 - Unpublish without losing history (Priority: P1)

A writer takes a published article down. Readers can no longer see it, but nothing is deleted: the last published snapshot and the publication date stay. The writer can later republish it.

**Why this priority**: Unpublishing must be a pure status change. Losing the last published content would make a mistaken take-down irreversible.

**Independent Test**: Publish, unpublish, and check that readers get "not found" while the writer still sees the version history, the snapshot content and the publication date. Publish again and check the publication date is the original.

**Acceptance Scenarios**:

1. **Given** a published article, **When** the writer unpublishes it, **Then** readers get "not found", and the status is "unpublished"; the snapshots, the live snapshot reference, the publication date and the draft are unchanged.
2. **Given** an article that is not currently published, **When** the writer tries to unpublish it, **Then** the request is refused with a clear message and nothing changes.
3. **Given** an unpublished article whose draft was edited, **When** the writer publishes, **Then** a new snapshot is created and the article is live again with its original publication date.
4. **Given** an unpublish and a publish arriving at the same moment, **When** they are processed, **Then** they are handled one after the other and either order leaves a valid state.

---

### User Story 5 - Version history, restore and safe deletion (Priority: P1)

A writer can see every snapshot of an article, newest first, open any of them, copy an old snapshot back into the draft (Restore), and delete snapshots that are not protected. The **protected snapshot** is the one the article currently points to as its live version; it stays protected after the article is unpublished.

**Why this priority**: History is the writer's safety net, and its protection rules are among the assessed edge cases.

**Independent Test**: Publish three versions, restore the first into the draft and check that the history is byte-for-byte the same and the status is unchanged; try to delete the protected snapshot and check it is refused; delete an older one and check it works.

**Acceptance Scenarios**:

1. **Given** an article with several snapshots, **When** the writer opens the history, **Then** snapshots are listed newest first, each with its number, title, creation time, and a mark showing which one is live; the body is not included in the list.
2. **Given** a snapshot, **When** the writer opens it, **Then** its full title, body and tags are shown.
3. **Given** a writer looking at a draft, **When** the writer restores a past snapshot, **Then** only the draft's title, body and tags are replaced, the draft's version number goes up by one, and nothing is published.
4. **Given** any article in any state (never published, published or unpublished), **When** a restore happens, **Then** every snapshot is identical before and after, and the status, live snapshot reference and publication date are unchanged.
5. **Given** a snapshot number the article does not have, **When** the writer restores or opens it, **Then** the response is "not found" and nothing changes.
6. **Given** the protected snapshot (live, or the last one live before the article was unpublished), **When** the writer tries to delete it, **Then** the system refuses with a clear message, and the snapshot still exists. This is enforced by the system itself, not only by hiding a button.
7. **Given** a snapshot that is not protected, **When** the writer deletes it, **Then** it is removed and the remaining snapshots are unchanged; its number is never reused.
8. **Given** a delete and a publish arriving at the same moment, **When** they are processed, **Then** the live reference never points at a missing snapshot and no server error occurs.

---

### User Story 6 - Detect conflicting edits (Priority: P1)

If two people (or two browser tabs) work on the same draft, a save based on an out-of-date view is refused instead of silently overwriting newer work. The writer is told what happened and can choose to reload the latest version or resend their own input.

**Why this priority**: Silent overwrites lose work, and conflict detection is an assessed invariant.

**Independent Test**: Open the same draft in two tabs, save in the first, then save in the second. The second save is refused with a clear conflict message, the first save's content is intact, and the second tab keeps what its writer typed.

**Acceptance Scenarios**:

1. **Given** two screens showing draft version 5, **When** the first saves (making version 6) and the second then saves, **Then** the second is refused as a conflict and the response carries the current version number; nothing is overwritten.
2. **Given** a conflict, **When** the writer's screen shows it, **Then** the text the writer had typed is kept, the writer is told the server copy changed, and they can reload the latest or resubmit their input against the new version.
3. **Given** an edit and a restore based on the same version, **When** both are sent, **Then** exactly one succeeds and the other is refused as a conflict.
4. **Given** a publish based on a version older than a saved edit, **When** it is sent, **Then** it is refused as a conflict and no snapshot is created, so a writer never publishes a draft they did not see.
5. **Given** successful edits, restores and snapshot-creating publishes, **When** the draft's version number is read, **Then** it has gone up by exactly one for each. It does not change on unpublish, on deleting a snapshot, or on a publish that creates nothing.

---

### User Story 7 - Publishing the same content twice creates no duplicate (Priority: P2)

If the draft is exactly the same as the live snapshot, publishing again does not create another snapshot. If the article had been taken down, the same action simply puts it back online.

**Why this priority**: An adopted optional feature. It makes accidental double-clicks harmless, but the core does not depend on it.

**Independent Test**: Publish, publish again without changes, and check the version count is still one. Unpublish, publish again without changes, and check the article is live again and the count is still one.

**Acceptance Scenarios**:

1. **Given** a published article whose draft equals the live snapshot, **When** the writer publishes, **Then** no snapshot is created, nothing changes, and the writer is told it was already up to date.
2. **Given** an unpublished article whose draft equals its last live snapshot, **When** the writer publishes, **Then** it goes back to published with no new snapshot and the original publication date.
3. **Given** a draft that equals an older (not live) snapshot but differs from the live one, **When** the writer publishes, **Then** a new snapshot is created, because only the live snapshot is compared.
4. **Given** a stale screen, **When** the writer publishes an unchanged draft, **Then** the out-of-date check still comes first and the request is refused as a conflict.

---

### User Story 8 - Writer area is protected (Priority: P2)

Everything a writer does (the writing screens and all the operations behind them) requires a username and password when authentication is on. It is always on in the deployed service; it can be switched off only for a local run. The public site and the public article endpoints never need it.

**Why this priority**: The assignment does not require sign-in, but the service is reachable from the internet, so without it anyone could edit, publish or delete. The core behaviour does not depend on it, so it follows the core stories.

**Independent Test**: Call every writer operation with no credentials, wrong credentials and right credentials; only the right ones work. Call public pages with and without credentials; they work either way.

**Acceptance Scenarios**:

1. **Given** no or wrong credentials, **When** any writer page or operation is requested, **Then** the response is "sign-in required" and the browser asks for credentials. The credentials are checked before anything else, so the answer is never "not found" or "invalid input".
2. **Given** the right credentials, **When** a writer uses the writer area, **Then** it works normally.
3. **Given** the public site or a public endpoint, **When** requested with or without credentials, **Then** it works the same.
4. **Given** the service starts in production with authentication switched off, or with authentication on but either credential empty, **When** it starts, **Then** it refuses to start.
5. **Given** a local run with authentication switched off, **When** a writer uses the writer area, **Then** it works with no sign-in, and the start-up log says clearly that authentication is off.
6. **Given** a new writer operation is added in the future, **When** nobody remembers to protect it, **Then** it is protected anyway, and an automated check fails if any writer operation can be reached without credentials.

---

### Edge Cases

- **Failure and crash during publish**: any failure at any step leaves no trace; the next publish still gets the next snapshot number without gaps from the failed attempt.
- **Two publishes at once**: exactly one wins; the other is told it is out of date (never a server error, never a duplicate snapshot).
- **Publish racing a delete**: the live reference never points at a deleted snapshot.
- **Unpublish then delete**: the last live snapshot stays protected, because unpublishing keeps it and the publication date.
- **Delete the only snapshot of an unpublished article**: refused, since it is the protected one; an article that has been published therefore never ends up with an empty history.
- **Restore on a never-published article, a published article and an unpublished article**: never changes status, live reference or publication date.
- **Restore or open a snapshot number that does not exist**: "not found", nothing changes.
- **Draft equals an old snapshot (not the live one)**: publishing still creates a new snapshot.
- **Draft with an empty body**: saving is allowed; publishing is refused until the body and title are filled in.
- **Slug limits**: a slug that is too long after a suffix is added is shortened so the result still fits; two creations racing for one slug end up with two different slugs, never an error.
- **Tags**: surrounding spaces are trimmed, letters are lowercased, duplicates are dropped (keeping order), and more than the allowed number is rejected.
- **Order of checks for a writer request**: sign-in first, then "does it exist", then "is the input valid", then "is the screen out of date", then business rules.
- **Unpublish a draft or an already-unpublished article**: refused with a clear message.
- **Hostile content**: raw HTML or script in an article's Markdown is never run in a reader's browser; links are limited to safe kinds.
- **Reloading after taking down**: the very next request already hides the article; nothing is kept in a cache.
- **Empty states**: an empty public list, an empty writer list and an article with no snapshots all show a friendly message, not an error.
- **Very large lists**: lists show at most 100 items per page of results.

## Requirements *(mandatory)*

### Functional Requirements

**Numbering.** This specification numbers requirements `FR-001`, `FR-002`, … and invariants `INV-001`, …; `docs/requirements.md` uses `FR-1`, … and `INV-1`, … Mapping: FR-001 ↔ FR-1; FR-002 ↔ FR-2; FR-003 ↔ FR-1, FR-2 and U3 to U5; FR-004 ↔ FR-14; FR-005 ↔ FR-15; FR-006 to FR-011 ↔ FR-3 (with R4, R5, U8); FR-012, FR-013 ↔ FR-4; FR-014 ↔ FR-5; FR-015 ↔ FR-6; FR-016 ↔ FR-7; FR-017, FR-018 ↔ FR-8; FR-019, FR-020 ↔ FR-9; FR-021 ↔ FR-16; FR-022 ↔ FR-10; FR-023, FR-025 ↔ FR-11; FR-024 ↔ FR-12; FR-026 ↔ R11; FR-027 ↔ U7; FR-028 to FR-031 ↔ FR-13; FR-032, FR-033 ↔ 3.3 and the error envelope; FR-034, FR-035 ↔ section 5; FR-036, FR-037 ↔ section 8; FR-038 ↔ section 7; INV-001 to INV-006 ↔ INV-1 to INV-6. The excluded AI feature (FR-17 in the docs) has no number here.

**Drafts and articles**

- **FR-001**: Writers MUST be able to create an article from a title, a slug, a Markdown body and tags; if the slug is already taken, the system MUST append a number to make it unique and MUST show the slug that was stored.
- **FR-002**: Writers MUST be able to edit an existing article's draft (title, body and tags); the slug MUST NOT be changeable after creation.
- **FR-003**: The system MUST validate input: the title is 1 to 200 characters and not only whitespace; the slug uses lowercase letters, digits and single hyphens and is at most 100 characters; there are at most 10 tags of 1 to 30 characters each, trimmed, lowercased and without duplicates; the body is at most 100,000 characters and MAY be empty in a draft.
- **FR-004**: Writers MUST be able to list all articles in any state, showing the draft title, slug, state, draft version and last-changed time, newest change first, at most 100 per page of results, optionally filtered by state; an unknown state value MUST be rejected.
- **FR-005**: The writer's edit screen MUST show a rendered preview of the Markdown that follows the same rendering and safety rules as the public site.

**Publishing**

- **FR-006**: Writers MUST be able to publish the current draft. A publish MUST create a new, numbered, immutable snapshot of the draft's title, body and tags, set the article's state to published, make the new snapshot the live one, and record the first publication date only if none exists.
- **FR-007**: A publish MUST be all-or-nothing, including through crashes and simultaneous requests, so that no state exists where an article is published without a live snapshot, is published but points at an old snapshot, or is not published but has a new live snapshot.
- **FR-008**: A publish MUST be refused when the draft's title or body is empty, creating nothing.
- **FR-009**: A publish MUST carry the draft version the writer was looking at and MUST be refused as a conflict if it no longer matches, creating nothing.
- **FR-010**: If the draft equals the current live snapshot (title, body and tags), a publish MUST NOT create a snapshot and MUST leave the publication date, live reference and draft version unchanged; if the article was unpublished, it MUST go back to published; the response MUST tell the writer that nothing new was created. Only the live snapshot is compared.
- **FR-011**: The publication date MUST be set once, at the first publication, and MUST NOT change afterwards.

**Unpublishing**

- **FR-012**: Writers MUST be able to unpublish a published article. Unpublishing MUST only change its state, hiding it from readers; it MUST keep every snapshot, the live snapshot reference, the publication date and the draft.
- **FR-013**: Unpublishing an article that is not published MUST be refused with a clear message.

**Versions**

- **FR-014**: Writers MUST be able to list an article's snapshots newest first, each with number, title, creation time and whether it is live, without the body.
- **FR-015**: Writers MUST be able to open any snapshot and see its full title, body and tags.
- **FR-016**: Writers MUST be able to restore a past snapshot into the draft. A restore MUST copy only title, body and tags, MUST NOT publish, MUST NOT create, change or delete any snapshot, and MUST NOT change the state, the live reference or the publication date in any state. It MUST carry the draft version the writer was looking at and be refused as a conflict if it does not match; on success the draft version goes up by one.
- **FR-017**: Writers MUST be able to delete a snapshot that is not protected. The **protected snapshot** is the one the article's live reference points at, including after the article is unpublished. Deleting it MUST be refused by the system with a clear message, independent of anything the screen shows. Snapshot numbers MUST NOT be reused after a deletion.
- **FR-018**: Deleting a snapshot MUST NOT race with a publish, an unpublish or a restore into a broken state; the live reference MUST never point at a missing snapshot, and the outcome MUST never be a server error.

**Concurrency**

- **FR-019**: The draft MUST carry a version number that goes up by one on each successful edit, restore and snapshot-creating publish, and does not change on unpublish, deleting a snapshot or a publish that creates nothing.
- **FR-020**: An edit, a restore or a publish based on an out-of-date draft version MUST be refused with a clear conflict message that includes the current version, and MUST change nothing. Unpublish and deleting a snapshot do not need a version.
- **FR-021**: After a conflict, the edit screen MUST keep the writer's unsent input, show that the server copy changed, and let the writer reload the latest or resubmit against the new version.

**Reading**

- **FR-022**: Readers MUST be able to list published articles (and only those), newest first publication date first, showing title, tags and publication date, plus an updated date for articles that have been republished (that is, whose live snapshot is not the first one, so its number is 2 or more; an unpublish followed by a publish that creates nothing is not a republish); at most 100 per page of results.
- **FR-023**: Readers MUST be able to open a published article and see the title, tags and body of its live snapshot, never the draft, even if the draft changed after publishing.
- **FR-024**: For an article that was never published, an article that was taken down, or an address that does not exist or is malformed, the system MUST give the same "not found" response with the same body, without error detail or draft content.
- **FR-025**: Public responses MUST contain only: address, title, tags, body (detail page only), publication date and live snapshot date. They MUST NOT contain draft fields, draft version, the article's last-changed time, its state or internal numbers.
- **FR-026**: Public pages MUST reflect a take-down on the very next request; nothing about published content may be kept in a cache, and writer responses MUST be marked as not to be stored by browsers or proxies.
- **FR-027**: Markdown MUST be rendered safely: raw HTML is not rendered and links are limited to web, secure web and mail addresses.

**Writer access**

- **FR-028**: When authentication is enabled, every writer screen and operation MUST require a username and password supplied through configuration, never written in the code or logged. Authentication is controlled by one explicit setting, MUST be enabled in production, and MAY be switched off only for a local run (so the assignment's "no sign-in" also holds on a machine that starts the project). Public pages, public endpoints and the service's liveness check MUST NOT require them.
- **FR-029**: A missing or wrong credential MUST always produce a "sign-in required" response that tells the browser to ask for the credentials, even for an article that does not exist (the order of checks is FR-033).
- **FR-030**: The service MUST refuse to start if authentication is enabled and either credential is empty, and in production it MUST also refuse to start unless authentication is enabled; when authentication is off, start-up MUST log a clear warning. In production it also MUST NOT publish its interactive API documentation, and MUST NOT allow another website to call it from a browser.
- **FR-031**: Writer operations MUST be protected by default, and an automated check, run with authentication enabled, MUST fail if any writer operation can be reached without credentials.

**Errors and consistency**

- **FR-032**: All errors MUST use one consistent shape with a code, a message and optional details, and the conflict response MUST include the current draft version.
- **FR-033**: Every writer request MUST be checked in this order: sign-in, existence, shape and validity of input, draft version, then business rules.

**Delivery and process**

- **FR-034**: From a fresh checkout, one short command that needs only Docker (`docker compose up --build`) MUST start the whole system (the database, its schema, the API and the web app). The project MUST also run without containers for the application (`make setup` and `make dev`) against any database named in configuration, and an assessor MUST be able to check the behaviour on the deployed site instead.
- **FR-035**: Automated tests MUST run with a single command (and, on a machine with only Docker installed, with one command that runs them in a container) and MUST cover every invariant, every lifecycle operation (publish, unpublish, restore, delete, concurrency) and the adopted optional features; tests MUST refuse to run against any database whose name does not end in `_test` or that is not local.
- **FR-036**: The specification, plan and task list MUST be committed before any implementation file, history MUST NOT be rewritten, and a script MUST verify that order.
- **FR-037**: The README MUST start with the assessor path (the deployed address; the credentials are shared outside the repository) and MUST describe how to run the project, the data model and why it was chosen, at least one design trade-off made under the time limit, what would be improved with more time, and a table of features with their status that says, for anything not done, what is missing and how it would have been built.

**Interface**

- **FR-038**: The interface MUST be minimal, clean and consistent in how it looks: readable from phone width to desktop width, usable with the keyboard with a visible focus, using one accent colour and generous whitespace, and showing friendly empty and error states. Styling is done after the functionality and must not delay it.

### Invariants

These must hold at every moment, and each one has at least one automated test.

- **INV-001 Snapshots never change**: once a snapshot exists, its content never changes; edits always go through the draft, and the data store itself refuses any change.
- **INV-002 Publish is atomic**: the state change, the new snapshot, the live reference and the publication date succeed or fail together, through crashes and simultaneous requests.
- **INV-003 The protected snapshot cannot be deleted**: the snapshot the live reference points at (also after unpublishing) is refused for deletion by the system itself.
- **INV-004 Restore never harms history**: a restore creates, changes and deletes no snapshot and changes no state; it only copies into the draft.
- **INV-005 Conflicting edits are detected**: a change based on stale data is refused with a clear conflict and never overwrites newer work.
- **INV-006 History survives unpublishing**: the snapshots and the publication date remain after a take-down and after republishing.

### Key Entities

- **Article**: one piece of documentation. It has an address (slug, fixed after creation), a state (never published, published or unpublished), a draft (title, body, tags), a draft version number used to detect conflicting edits, a first publication date, a live-snapshot reference, and a counter that numbers its snapshots so numbers are never reused.
- **Draft**: the editable working copy held with the article. It is never shown to readers.
- **Snapshot (version)**: a permanent, numbered record of the title, body and tags at the moment of a publish. It belongs to one article and never changes. One snapshot per article is the live one (the protected one).
- **Writer**: a member of the small internal team who signs in with a shared username and password.
- **Reader**: any visitor who is not signed in and can only see published content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every one of the six invariants is covered by at least one automated test, and all tests pass from one command on a clean checkout.
- **SC-002**: In a repeated test where two publishes start from the same screen state at the same moment, in 100% of runs exactly one succeeds and the other is refused, with no server error and unbroken snapshot numbering.
- **SC-003**: In a test that fails a publish at each of its steps in turn, in 100% of cases the article's state, live snapshot, publication date, draft version and snapshot list are identical to before.
- **SC-004**: After any number of draft edits following a publish, 0 public responses contain any draft text, and the public detail always matches the live snapshot.
- **SC-005**: A never-published article, a taken-down article and a made-up address produce responses that are identical (same status and same body) in 100% of checks.
- **SC-006**: A restore leaves the full snapshot list and the article's state, live reference and publication date identical in 100% of checks, in all three states.
- **SC-007**: Trying to delete the protected snapshot is refused in 100% of attempts, including right after an unpublish and while a publish is happening.
- **SC-008**: After an unpublish, the very next public request no longer shows the article.
- **SC-009**: A writer can create an article and publish it for the first time in under 3 minutes, and can recover from an edit conflict without retyping.
- **SC-010**: With authentication enabled, every writer operation refuses a request with no or wrong credentials in 100% of checks, and no public page ever asks for credentials; with it switched off in a local run, every writer operation works with no credentials.
- **SC-011**: One command shows that the specification, plan and task list were committed before any implementation file.
- **SC-012**: An assessor can verify the main behaviours on the deployed site without installing anything.
- **SC-013**: On a machine with only Docker installed, one command starts the whole system from a fresh checkout, and a writer can then create and publish a first article.

## Assumptions

- The writers are a small, trusted internal team who share one username and password; there are no roles or per-person accounts.
- Readers are anonymous and need no sign-in.
- Authentication is outside the assignment's scope; the shared username and password is an addition so that the deployed service cannot be changed by anyone on the internet. For a local run it can be switched off, because the assignment says writers need no sign-in.
- Writers use a modern desktop browser; the interface is minimal (an edit form, an article list and a version history panel), and its looks are not part of the assessment.
- All times are stored in UTC and shown in the reader's or writer's local time.
- Both adopted optional features are in scope: publishing the same content twice creates no duplicate (User Story 7), and a taken slug gets a number appended (User Story 1).
- The service runs against a single database. Production, development and test databases are separate, and tests never touch any other.
- Assessors can check the work in either of two ways: on a deployed copy (they cannot reach the authors' database, so the deployed copy and its database stay running during the assessment), or on their own machine with one command that needs only Docker.
- The data model, the programming interface and the exact SQL are decided in the plan; `docs/nextjs-fastapi-architecture.html` and `backend/db-automation-apply/001_schema.sql` are the starting drafts.
- Where this specification and `docs/` disagree, this specification wins and `docs/` is corrected.

## Out of Scope

- Sign-in for readers, roles, several accounts, multi-tenancy and per-person access control.
- Rich Markdown extensions, custom components and in-browser visual editors (a plain input and a preview are enough).
- File and media uploads, search, large-scale pagination and any caching layer.
- Deleting an article itself.
- The optional features Save as Version and Diff View.
- Production deployment automation, CI/CD and infrastructure as code (a simple deployment is provided as a low-priority extra and is not part of the assessed scope).
- **AI-generated drafts (called AI-1 here; FR-17 in `docs/requirements.md`)**: not planned; it may be added only if everything else is finished, and it would never save or publish anything by itself.
