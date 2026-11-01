# Quickstart results

Run of `quickstart.md` scenarios 1 to 10 against a **clean copy of the repository** (no `node_modules`, `.venv`, `.next` or `.env`; `cp .env.example .env` then `docker compose up --build`), with only Docker needed. The API was called with a script (`urllib`) and the public pages were fetched from the web app on port 3000.

- Scenarios 1 to 8 and 10 ran with the writer login **off** (the local default). Scenario 9 ran on a second fresh stack with `BASIC_AUTH_ENABLED=true` (credentials passed on the command line, not stored in any file); the whole script was run again against it as well and also passed.
- Start-up from the clean copy took about 24 seconds with Docker's layer cache warm.

| Scenario | Check | Expected | Observed | Result |
|---|---|---|---|---|
| 1. Create and edit a draft | create | 201, draft_version 1, status draft | 201, v1, draft | pass |
| 1. Create and edit a draft | edit | 200, draft_version 2 | 200, v2 | pass |
| 1. Create and edit a draft | public list hides the draft | [] | [] | pass |
| 1. Create and edit a draft | slug collision | stored slug guide-2 | guide-2 | pass |
| 1. Create and edit a draft | PATCH with slug | 422 | 422 | pass |
| 2. Publish, and what readers see | publish | 201, created, version 1 | 201, created=True, v1 | pass |
| 2. Publish, and what readers see | public shows published text | Version one! | Version one! | pass |
| 2. Publish, and what readers see | list: updated_at null | null | None | pass |
| 2. Publish, and what readers see | web page shows published text | contains 'Version one!' not 'Draft only' | ok | pass |
| 3. Republish keeps the first date | republish | 201, version 2, published_at unchanged | 201, v2, same_date=True | pass |
| 3. Republish keeps the first date | list shows updated_at | not null | 2026-10-31T14:31:16.626999Z | pass |
| 4. Unpublish keeps history | unpublish | 200, unpublished | 200, unpublished | pass |
| 4. Unpublish keeps history | three public misses identical | 404 x3, one body | [404, 404, 404], bodies=1 | pass |
| 4. Unpublish keeps history | history and published_at kept | 2 snapshots, same date | 2, same=True | pass |
| 4. Unpublish keeps history | unpublish twice | 409 not_published | 409 not_published | pass |
| 5. Restore never harms history | restore | 200, draft_version +1, history/status/date unchanged | 200, v6, same_history=True, status=published | pass |
| 5. Restore never harms history | restore did not publish | public still version 2 | Draft only text | pass |
| 6. The protected version cannot be deleted | delete live | 409 version_is_live | 409 version_is_live | pass |
| 6. The protected version cannot be deleted | delete live after unpublish | 409 version_is_live | 409 version_is_live | pass |
| 6. The protected version cannot be deleted | delete older | 204 | 204 | pass |
| 6. The protected version cannot be deleted | delete missing number | 404 | 404 | pass |
| 6. The protected version cannot be deleted | number not reused | version 3 | v3 | pass |
| 7. Conflicting edits | second stale save | 200 then 409 version_conflict with current version | 200 then 409 version_conflict {'current_draft_version': 9} | pass |
| 7. Conflicting edits | nothing overwritten | Tab one | Tab one | pass |
| 7. Conflicting edits | stale publish | 409 | 409 | pass |
| 7. Conflicting edits | no snapshot created | 3 snapshots... (v2,v3) | 2 | pass |
| 8. Idempotent Publish | publish unchanged | 200, created false, version 2 | 200, created=False, v2 | pass |
| 8. Idempotent Publish | still two snapshots | 2 | 2 | pass |
| 8. Idempotent Publish | unpublish then publish unchanged | 200, created false, published again | 200, created=False, published | pass |
| 8. Idempotent Publish | still two snapshots | 2 | 2 | pass |
| 9. Writer area is protected | writer routes | 401 (www-authenticate Basic), 401, 404, public 200 | 401 None, 401, 404, 200 | pass |
| 9. Writer area is protected | web /studio asks for credentials | 401 + WWW-Authenticate | 401 None | pass |
| 10. No caching | gone on the very next request | 200 then 404 | 200 then 404 | pass |

## Scenario 11 (browser run)

Run later, in headless Chrome driven through the real screens against the running Docker system (writer login off).

| Step | Expected | Observed | Result |
|---|---|---|---|
| Open `/studio` | A "New article" button is shown | button present | pass |
| Press "New article" | The editor opens at `/studio/new` | `/studio/new` | pass |
| Type a title | The slug fills in from the title | `browser-flow-test` | pass |
| Type a Markdown body | The preview renders it | heading rendered in the preview | pass |
| Press "Save & publish" | The article is created and published; the editor opens | `/studio/8`, status Published | pass |
| Edit the title | The button reads "Save & publish" | `Save & publish \| Unpublish` | pass |
| Press "Save & publish" again | Saved and published as version 2 | "Saved and published as version 2." | pass |


## Scenario 12 (AI body generation, optional extra, streamed)

Run with a **local stand-in for the model** (a small server answering `/v1/messages` as a server-sent stream, one piece every half second, reached through `ANTHROPIC_BASE_URL`), so the real SDK built and sent the request and read a real stream, but no real model was called and no key was used.

| Step | Expected | Observed | Result |
|---|---|---|---|
| Default settings (AI off): API | status says off; the draft operation answers 503 `ai_disabled` | `{"enabled":false}`, 503 `ai_disabled` | pass |
| Default settings (AI off): screen | the button is visible but disabled, with a note on how to switch it on | shown disabled with the note | pass |
| AI on: empty title, then a title and a tag | disabled, then enabled | as expected | pass |
| API stream | `text/event-stream`, `no-store, no-transform`, pieces arrive over time, then `done` | seven `delta` events at 0.5 s intervals, then `done` | pass |
| Request that reached the model | model `claude-sonnet-4-6`, token cap, streaming, last turn from the user, no sampling parameters, no thinking | exactly that | pass |
| In the browser: after pressing the button | the body **grows progressively**; a Stop button is shown while it writes and disappears at the end | body length 0 → 15 → 31 → 59 → 81 → 105 → 129 → 135 characters; 8 distinct lengths | pass |
| Title and tags | unchanged | unchanged | pass |
| Nothing created by generating | article count unchanged | 9 before, 9 after | pass |
| In the browser: Stop part-way | the text that arrived stays and no more arrives; the button returns | 31 characters kept, still 31 after 2.5 s; "Stopped. What had arrived was kept" | pass |
| Sixth request within a minute (API) | 429 | 429 after five | pass |

**Not run**: a call to the real model. It needs a key and costs a few cents, so it is a manual step (`quickstart.md`, scenario 12). The request shape and the stream handling were checked against the SDK itself and the model's documented rules, not against the live service.

## Writer screens in a real browser (headless Chrome, local Docker system, writer login off)

An article with versions 1 and 2 was set up through the API, then the screens were driven by script (clicks and typing in the real page). This covers the screen side of scenarios 5, 6, 7 and 4.

| Step | Expected | Observed | Result |
|---|---|---|---|
| History panel | version 2 marked Live, version 1 listed | as expected | pass |
| Delete on the live version | the button is disabled | disabled | pass |
| View version 1 | its full text is shown | shown | pass |
| Restore version 1 | the draft holds version 1's text; status and live version unchanged; the public page still shows version 2 | all as expected | pass |
| Another writer saves first, then this tab saves | the screen says the server copy changed; my unsent text stays in the form; the server copy is not overwritten | all as expected | pass |
| "Resubmit mine against the new version" | my text is saved; the conflict message goes away | saved; message gone | pass |
| Delete version 1 (confirm accepted) | version 1 is gone, the live version 2 remains | as expected | pass |
| Unpublish | status unpublished, history kept, public page 404, the Unpublish button disabled | as expected | pass |
| Publish again | version 3 goes live | live version 3 | pass |

18 of 18 checks passed.

## The deployed site (reported by the owner)

Both services run on Cloud Run (automatic deploys from GitHub). The author checked the public side from outside (public list, 404s, 401 for the writer area and the API, security headers, API to database). The owner, who holds the writer credentials, then reported that they ran the quickstart scenarios on the deployed site, tried the AI button against the real Claude model, saw the browser's own sign-in box, and checked the first-article-in-under-three-minutes goal (SC-009). These four were done by the owner and are not recorded in detail (no timings or transcripts), so they are listed here as reported, not as measured by the author.

## What this run did not cover

- **Two real tabs for scenario 7.** The conflict screen was driven in one browser page while the "other writer" saved through the API, which is the same server-side situation; two separate tabs were not used.
- **Scenario 9 in a browser (author).** The web app was checked to answer `/studio` with 401 and `WWW-Authenticate` when the login is on; the author did not observe the sign-in prompt. The owner reports seeing it on the deployed site.
- **SC-009 (first article published in under 3 minutes by hand)** was not timed by the author. The owner reports that this goal is met on the deployed site (not recorded in detail).
- **The deployed site (Cloud Run).** The scenario results above are from the local run. The deployed site is described only in the section "The deployed site (reported by the owner)".
