# JobTracking — Architecture

A personal, single-user job search helper. It finds the jobs I have the best chance of hearing back from, sends me a short list of picks, and tracks every application through to an outcome.

> This document records **what** we decided and **why**. Bigger individual decisions also get an Architecture Decision Record (ADR) in [`docs/adr/`](adr/).

---

## 1. Goals

### MVP
- On demand, collect current openings from job boards and target companies.
- Filter out jobs that don't match my profile.
- Rate each promising job against my resume for **chance of hearing back**.
- Send the top 3–5 picks to Discord.
- Track applications: applied, tracking link, status, notes, history.
- Remind me which applications need a follow-up.

### Future
- Tailor my resume and write a cover letter per job.
- Pre-fill application forms (I always submit myself).
- Draft follow-up emails to recruiters (I approve before sending).
- Local dashboard and insights on what's working.

### Non-goals
- Multiple users, accounts, or hosting for others.
- Scraping sites whose terms forbid it (LinkedIn, Indeed).
- Submitting applications or sending emails without my explicit approval.

---

## 2. Key decisions

| Area | Decision | Why |
|---|---|---|
| Language | **Python 3.13** | Strong libraries for every phase: HTTP, the Claude SDK, browser automation (Playwright), document generation |
| How it runs | **Manually, on my laptop** (`jobhunt run`) | No server, no scheduler, nothing to host or pay for |
| Interface | **Command line** now; optional **local web page** later | Don't build a UI before it's needed |
| Notifications | **Discord webhook** to a private channel | One HTTP call; shows up on my phone; no bot to host |
| Storage | **SQLite** (one file), accessed only through a repository interface | No server; plenty for one user; swappable later |
| Job sources | **Public company job board APIs** (Greenhouse, Lever, Ashby) + **aggregators with APIs** (Remotive, Adzuna) | Official, stable, legal; full job descriptions |
| Fit rating | **Claude API**: structured output, each job rated once | Judges fit like a recruiter would; cost controlled by pre-filtering |
| Config | `config.yaml` (settings) + `.env` (secrets), both git-ignored; `.example` templates committed | Personal data and keys never reach git |
| Resume | Markdown for the MVP → **structured master resume** before tailoring | Tailoring edits data, not formatting |

---

## 3. Architecture

### Layers (dependencies point inward only)

```
        cli/  (and later web/)          ← user interface: parse input, show output
              │
        application/                    ← use cases: coordinate the steps of a task
              │
   ┌──────────┴──────────┐
 domain/              ports/            ← business rules  |  interfaces
                         ▲
                     adapters/          ← real integrations: job boards, SQLite, Claude, Discord

        bootstrap.py                    ← the ONLY place concrete adapters are chosen and wired
```

**Rules**
1. `domain/` imports nothing from other layers and does no I/O.
2. `application/` depends only on `domain/` and `ports/`, never on a concrete adapter.
3. 3. `adapters/` implement `ports/`; they are the only code that touches the network, disk, or external services. Configuration loading (reading config.yaml / .env) is treated as an adapter concern and lives at this boundary.
4. `cli/` is thin: no business logic.
5. Dependencies are passed in through constructors and wired in `bootstrap.py`.

**What this buys us**
- **Testability:** use cases run against fakes, with no network or database.
- **Replaceability:** a new job board, database, or notification channel is a new adapter; nothing else changes.
- **Single responsibility:** each module has one reason to change.

### Main flow: `jobhunt run`

```
fetch (all sources) → save new / skip duplicates → filter by profile
   → pre-rank (keywords + freshness) → rate top N with Claude (once per job)
   → final rank (fit score + freshness boost) → top picks
   → Discord + console → list follow-ups due
```

- A failing source or rating never stops the run; it's reported at the end.
- Freshness boost: applying early is one of the strongest predictors of hearing back.

---

## 4. Folder structure

```
.github/workflows/ci.yml   CI: format, lint, types, tests on every push, and on PRs targeting develop/production
docs/ARCHITECTURE.md          this document
docs/adr/                     one file per significant decision
scripts/                      developer tools (e.g. branch-name check), not app code
src/jobhunt/
  __main__.py                 `python -m jobhunt` entry point
  bootstrap.py                wires adapters to use cases
  domain/                     Job, JobStatus + transition rules, domain errors
  ports/                      JobSource, JobRepository, Clock (later FitScorer, Notifier)
  application/                use cases: fetch_jobs, track_application (later rank_jobs...)
  adapters/
    http/                     shared HTTP client: timeouts, retries, user agent
    sources/                  one module per job board + shared parsing helpers
    storage/                  in-memory repository (tests) + SQLite repository + migrations
  config/                     load and validate config.yaml / .env
  cli/                        commands
tests/
  unit/                       fast, isolated; mirrors src/
  contract/                   shared suite every JobRepository must pass
  integration/                real SQLite file; adapters against recorded responses
  e2e/                        CLI end to end against fixtures + temp DB
  fakes/                      reusable test doubles
  fixtures/                   recorded API responses
```

**Where future features go:** more sources → `adapters/sources/`; filtering/ranking → `domain/` + `application/`; Claude → `ports/fit_scorer.py` + `adapters/scoring/`; Discord → `ports/notifier.py` + `adapters/notify/`; resumes → `domain/resume.py` + `adapters/documents/`; dashboard → `src/jobhunt/web/`.

---

## 5. Data model (SQLite)

**jobs**: one row per posting
- Identity: `id` (hash of source + external id), `source`, `external_id`
- Posting: `company`, `title`, `url`, `location`, `remote`, `description`, `posted_at`, `salary_min`, `salary_max`
- Tracking: `first_seen`, `last_seen`, `status`, `recommended_on`, `applied_at`, `tracking_url`, `contact`, `notes`
- Rating: `prefilter_score`, `fit_score`, `fit_details` (JSON), `rated_at`

**events**: full history of status changes (`job_id`, `at`, `status`, `note`)

**Statuses:** `new → recommended → applied → interviewing → offer`, plus `rejected`, `ghosted`, `skipped`. Allowed transitions are enforced in `domain/`.

**Schema changes:** numbered SQL migrations (`0001_initial.sql`, …) tracked in a `schema_version` table; existing files are never edited.

**Later:** `artifacts` (tailored documents per job), `emails` (follow-up drafts and sends).

---

## 6. Testing strategy

| Level | Scope | Tools / approach |
|---|---|---|
| Unit | Domain rules, ranking, filtering, use cases | pytest + fakes; no I/O; the majority of tests |
| Contract | Every `JobRepository` implementation | One shared suite run against in-memory and SQLite |
| Integration | SQLite repository, migrations, source parsing | Temp database file; recorded JSON responses |
| End-to-end | CLI commands | Fixture source + temp database |
| Live | Real job boards, Claude, Discord | Marked `live`; opt-in only; never in CI |

- External APIs are **never** called in automated tests.
- For the Claude rating, prompt building and response parsing are tested; the API call is faked.
- Coverage target: 90%+ on `domain/` and `application/` (enforced once real code exists).

---

## 7. Quality standards and workflow

**Tooling** (versions locked in `uv.lock`; the same for local runs and CI)
- `uv`: Python version, virtual environment, dependencies
- `ruff`: formatting + linting
- `mypy --strict`: type checking
- `pytest` + `pytest-cov`: tests and coverage
- `pre-commit`: runs checks on every commit; unit tests on every push

**Safety net**

| When | Check | Blocks? |
|---|---|---|
| `git commit` | Format, lint, types, commit message, branch name, no secrets | Yes |
| `git push` | Unit tests | Yes |
| On GitHub | Full checks on a clean machine (CI) | Marks the PR red |
| Merge | PR required; CI must pass (branch protection) | Yes |

**Branches**
- `develop`: integration branch; all work merges here through PRs.
- `production`: stable releases; updated from `develop`.
- Work branches: `type/short-description`, e.g. `feature/jt-1-greenhouse-jobs`, `fix/duplicate-jobs`.
- No direct commits to `develop` or `production`.

**Commits:** [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `test:`, `refactor:`, `docs:`, `chore:`, `ci:`, `build:`. Imperative mood, one logical change per commit.

**Stories:** tracked as GitHub issues `JT-<n>` on the project board. PRs reference their story (`Closes #<issue>`).

---

## 8. Secrets and privacy

- Secrets (`ANTHROPIC_API_KEY`, `DISCORD_WEBHOOK_URL`, `ADZUNA_APP_ID/KEY`) live only in `.env`.
- Personal data (`config.yaml`, `resume.md`, `data/`, generated documents) is git-ignored.
- `pre-commit` blocks committed private keys; config is validated at startup.

---

## 9. Cost control (Claude)

- Only jobs that pass the filters and pre-ranking are rated (maximum per run is configurable; default 35).
- Each job is rated once; the result is stored and reused.
- The resume and profile are sent as a cached prompt prefix.
- Token usage is logged per run.
- Rough cost: about $1 or less per run.

---

## 10. Roadmap

| Phase | Stories | Outcome |
|---|---|---|
| Foundation | JT-0 | Project setup and quality safety net |
| MVP | JT-1 … JT-13 | Find, filter, rate, pick, notify, track, follow-up reminders |
| 2 – Tailoring | JT-14 … JT-17 | Master resume, tailored resume + cover letter, 5–10 picks |
| 3 – Assisted apply | JT-18, JT-19 | Pre-filled forms (I submit), screening answer bank |
| 4 – Follow-ups | JT-20, JT-21 | Contact finding, approved follow-up emails |
| 5 – Insights | JT-22, JT-23 | Local dashboard, what's-working analytics |

**MVP build order:** JT-0 → 1 → 2 → 3 → 4 → 5 → 10 → 11 → 12 → 6 → 7 → 8 → 9 → 13.

---

## 11. Risks and constraints

| Risk | Mitigation |
|---|---|
| A job board changes its API | Each source is isolated; parsing is tested against recorded fixtures; a failure skips that source only |
| Fit ratings are inaccurate | Reasons and gaps are shown with every score; thresholds are configurable; review picks before applying |
| API cost grows | Pre-filtering, rate-once caching, configurable cap |
| Auto-apply submits something wrong | Submission is always manual |
| Follow-up email lands badly | Every email needs my approval; sent from my own account |
