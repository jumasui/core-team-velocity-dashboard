# Core Team velocity dashboard

The local snapshot dashboard is ready. It covers November 16, 2025 through November 16, 2026, 11:36 a.m. Pacific.

Open `dashboard.html` in your evidence directory after rebuilding. It loads entirely locally without network requests.

## Standalone checkout

Requires Python 3.11+, Node.js for JavaScript tests, and authenticated GitHub CLI for collection.
Install verification dependencies with `python -m pip install -r requirements-dev.txt`, then `python -m playwright install chromium`.
Set `JIRA_PR_DATA_DIR` to your local evidence directory; raw evidence and the generated dashboard are not committed.
Without that variable, the original sibling path `../core-team-velocity-analysis/evidence/jira-pr-dashboard` is preserved.
For this workspace, use `/Users/jumasui/Documents/ChatGPT/Quit Fund 3/core-team-velocity-analysis/evidence/jira-pr-dashboard`.
Fresh collection requires the external Jira Ops CLI and its local authentication configuration.
Set `JIRA_OPS_CLI` to its `jira_cli.py` path; the default is `~/.codex/skills/jira-ops/scripts/jira_cli.py`.
Neither credentials nor the external Jira Ops implementation are included in this repository.

A critical part of understanding Core Team time on issues is examining the pull requests those Jiras generate. Reliable comparisons require clear Jira-to-PR links; missing or ambiguous associations can produce inaccurate conclusions.

PR turnaround and review times should also be examined on their own, alongside Jira completion times. Missing links remain visible coverage gaps.

Core Team Owned refers to work tracked on Jira board 4073 and PRs directly linked to that work. Repository ownership is classified separately.

## What it shows
- Frequency histograms for Jira milestones, cumulative stage time, PR lifetimes and review-round response time.
- PR opening-to-merge, opening-to-closure, open age, and individual human review rounds.
- Repository distribution with a marked cherry-pick/backport filter.
- Three Jira ownership groups, plus PR timings by repository ownership.
- Ticket and PR drilldowns, explicit prerequisites, source coverage and access gaps.

Core-owned names are ai-studio, ai-ui, ai-canvas-ui, and ai-splunk-terraform within Cisco’s two GitHub organizations.
The user also confirmed historical ai-studio-ui and aispg-splunk-terraform were Core-owned.

Time bands end at 1, 2, 4, 8, 16, then advance linearly: 32, 48, 64, 80… days/hours.
The first 0–1 band includes zero and short durations. Tail bands have fixed width 16; longer charts scroll horizontally.
Counts and percentages label every Core Team Owned bar, including the first two. All time-band boundaries are labeled.
Blue bars represent Core Team Owned Jiras or their linked PRs; the amber line represents the rest of AISTUDIO, excluding saved board issue keys.
Percentages use each cohort's measured sample. Ownership panels share time bands and percentage scales.

Duration charts require Done at the original cutoff and a completion during the study year; every resolution qualifies.
PR charts require direct associations to those Done Jiras. Dependency links remain ownership context, outside PR counts.
The Done-rate chart uses all selected Jiras created during the study year, including unfinished work, as its denominator.
Its numerator includes those that reached Done and were reopened; those cases are shown separately from Done-at-cutoff tickets.

## Coverage

Board evidence contains 3,630 Jira candidates, 10,433 status changes and 2,396 accessible linked PR timelines.
Observed associations cover 1,449 board tickets. The remaining 2,181 tickets stay outside ownership comparisons.
Some tickets legitimately require no PR; missing associations do not establish missing code or incomplete work.

Two PR URLs return HTTP 404. Seven tickets have truncated comment collections. Jira remote links were not exhaustively collected.
Body-only Jira mentions remain candidates. Explicit prerequisites are followed one hop; unknown prerequisite repos remain coverage gaps.

The org comparison adds 23,326 candidate Jiras outside the saved board scope.
Default Story/Bug/Task duration cohorts contain 2,325 board Jiras and 8,353 benchmark Jiras that are Done at cutoff.
Missing links and inaccessible PRs remain excluded from PR timing samples; benchmark coverage appears in the dashboard.

The current board filter, status mapping and ownership baseline are applied retrospectively.
Ownership comparisons are descriptive and unadjusted; they do not establish that another team caused a delay.

## Rebuild from saved evidence

Run from this repository's root, with saved evidence available in `JIRA_PR_DATA_DIR`:

```sh
python metrics.py
python org_baseline.py --build-only
python render.py
python -m unittest discover -s . -p 'test_*.py'
node --test test_histogram.cjs test_cohorts.cjs
python verify.py
```

Verification requires the installed Python Playwright package and Chromium. Collection uses the existing Jira Ops configuration and GitHub CLI accounts.
No credentials are embedded in source files or the dashboard. TLS verification remains enabled in the authenticated API clients.
Untrusted text is rendered with DOM text APIs; embedded JSON escapes script delimiters.

## Refresh collection

The collector is pinned to this study’s dates. Review date boundaries before collecting a different reporting period.
Use `python audit.py jira` first, then each organization name as the source argument.
Switch GitHub CLI to `jumasui_cisco` for `cisco-aispg` and `jumasui` for `cisco-sbg`.
Run `metrics.py`, then `reviews.py ORGANIZATION` under each corresponding account, then rebuild and verify.
For the org benchmark, collect `org_baseline.py`, then run `reviews.py ORGANIZATION --organization` under each matching account.
The completed snapshot restored the original active account, `jumasui_cisco`.

Scheduled refresh and shared hosting are separate deployment work. The current deliverable is a saved, local dashboard.
