# JobTracking — Architecture & Plan

## Context
The repo is empty (only a README). The goal is a personal, single-user job application helper.
- **MVP:** each time you run it, it pulls jobs, picks the 3–5 with the best chance of hearing back, posts them to Discord, and lets you track your applications.
- **Future:** pick 5–10 jobs, tailor the resume and cover letter, apply, log the tracking URL, and send follow-up emails later.

This document records the architecture decisions. It's a plan only; no code yet.

## Decisions

| Area | Decision | Why |
|---|---|---|
| Language | **Python 3.11+** | Best tools for every phase: `httpx` (APIs), Claude SDK, Playwright (auto-apply later), `python-docx` / HTML→PDF (resumes). One language. |
| How it runs | **Manual, on your laptop:** `jobhunt run` | You chose on-demand. No server, no cron, nothing to host. |
| Interface | **Command line now** (`argparse`, no extra framework); **small local web page later** (Streamlit or FastAPI+HTMX) over the same database | Avoids building UI before you need it. |
| Daily picks | **Discord webhook** (post to your private channel) | A webhook is one HTTP POST. No bot hosting needed, and it shows up on your phone. Also printed to the console. |
| Storage | **SQLite** (`data/jobs.db`), all access through one `db.py` module | One file, no server, plenty for one person. Easy to swap later. |
| Job sources | **Company job boards:** Greenhouse, Lever, Ashby (public JSON, full descriptions; you list target companies). **Aggregators:** Remotive (remote software) + Adzuna (city search, free key) | Official APIs only. **No LinkedIn/Indeed scraping**: their terms ban it, they block it, and you risk your account. |
| Ranking | Cheap filter → Claude scores the top ~30–40 → final rank = fit score + freshness bonus | The filter keeps cost at roughly ≤$1 per run. Freshness matters a lot for hearing back. |
| Secrets/config | `config.yaml` (profile, sources, limits) + `.env` (API keys, Discord webhook URL), both gitignored; commit `config.example.yaml` | Personal data and keys stay out of git. |
| Resume | `resume.md` now. **Before phase 2, move to structured `resume.yaml`** rendered through a template | Tailoring then edits data, not formatting. This is the key decision for the future features. |

## Components (target layout)
```
jobhunt/
  cli.py          # run | list | show | apply | status | note | stats
  config.py       # loads config.yaml (pydantic)
  models.py       # Job dataclass, HTML→text, date parsing
  db.py           # SQLite schema + all queries (only module that touches SQL)
  sources/        # one module per source: fetch() -> list[Job]
    greenhouse.py lever.py ashby.py remotive.py adzuna.py
  filters.py      # hard filters (title/location/age/salary) + rough relevance score
  scorer.py       # Claude fit scoring → structured result
  notify.py       # Discord webhook + console output
config.example.yaml  resume.example.md  .env.example
tests/            # parsers tested against saved JSON fixtures; filters; db
```

## Data model (SQLite)
- **jobs:** id (hash of source+external_id), source, company, title, url, location, remote, description, posted_at, salary_min/max, first_seen/last_seen, prefilter_score, fit_score, fit_json, status, recommended_on, applied_at, tracking_url, contact, follow_up_on, notes.
- **events:** job_id, timestamp, status, note. Full history, so you can ask questions like "which kinds of applications got replies?"
- **Statuses:** new → recommended → applied → interviewing → offer; plus rejected / ghosted / skipped.
- Future columns/tables (phase 2+): `artifacts` (paths to tailored resume/cover letter per job), `emails` (follow-up drafts/sends).

## What `jobhunt run` does
1. Fetch from every configured source. Each source fails on its own without stopping the run.
2. Normalize and save new jobs; skip duplicates by id. Refresh `last_seen` on existing ones.
3. Hard filters: target titles (e.g. "software engineer", "backend"), excluded keywords, remote **or** your city, max age (14 days), salary floor.
4. Rough relevance score (skill keywords + freshness) → keep the top N (default 35) that haven't been scored yet.
5. **Claude scoring** (`claude-opus-5-5` via the Anthropic SDK, structured output, effort `medium`, a few calls in parallel, fallback on refusal). Your resume and profile go in a cached system prompt; the job posting is the user message. It returns: `fit_score` 0–100, `callback_likelihood` (low/med/high), must-haves met/missing, seniority match, red flags, one-line pitch, resume tweak ideas. Saved, so no job is scored twice.
6. Rank = fit_score + freshness bonus (+8 if ≤2 days, +4 if ≤5, −6 if >10); drop anything under `min_fit_score`.
7. Take the top `daily_count` (3–5) not yet shown to you → mark `recommended` → post to Discord (one message per job: title, company, location, score, why, gaps, apply link, short id) and print to the console.
8. Also list **follow-ups due** (applied more than N days ago with no status change). Because you run it manually, this replaces a scheduler.

## Tracking commands
`jobhunt list [--status applied]`, `jobhunt show <id>`, `jobhunt apply <id> --url <tracking> [--contact email]`, `jobhunt status <id> interviewing|rejected|...`, `jobhunt note <id> "..."`, `jobhunt stats` (counts by status, reply rate).

## Roadmap
1. **MVP (this plan):** sources, database, filtering, Claude scoring, Discord, command-line tracking.
2. **Tailoring:** resume.yaml → Claude produces a per-job variant + cover letter → rendered to PDF/DOCX in `output/<job-id>/` → you review.
3. **Assisted apply:** Playwright fills in Greenhouse/Lever/Ashby forms; **you click submit** (CAPTCHAs, custom questions, and the risk of a wrong submission make full auto risky). Logs the tracking URL.
4. **Follow-ups:** at each run, draft follow-up emails for due applications (Gmail API, your own address) for you to approve. Recruiter contact found best-effort (posting text, or added manually).
5. **Optional local web page** over the same database once the command line gets tedious.

## To fill in before building
- Your city (for Adzuna `where` and the location filter), and target titles and skills.
- Your list of target companies (their Greenhouse/Lever/Ashby board names).
- Keys: `ANTHROPIC_API_KEY`, `DISCORD_WEBHOOK_URL`, optional `ADZUNA_APP_ID/KEY`.

## Verification (when built)
- `pytest`: each source parser against saved sample JSON; filter edge cases; database upsert/dedupe and status changes.
- `jobhunt run --dry-run`: fetch + filter + score with no Discord post; check the console output.
- Real run against 2–3 known company boards; confirm the Discord messages arrive and `jobhunt apply/status/list` update the database correctly.
- Cost check: log token usage per run; adjust `max_to_score` if it's too high.
