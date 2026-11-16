# Board 4073 delivery dashboard

Build an auditable yearly dataset before comparing ownership groups.
Evidence lives in `core-team-velocity-analysis/evidence/jira-pr-dashboard/` as requested.

## Agreed scope
- Package source in a private, user-owned GitHub repository; keep raw evidence and generated dashboards local.
- Support standalone checkouts through JIRA_PR_DATA_DIR and JIRA_OPS_CLI path overrides.
- Do not publish this work to the Behavioral Metrics page; the user explicitly revoked that destination.
- Introduction: reliable velocity comparisons require clear Jira-to-PR links; analyze linked PR turnaround and review times separately.
- Label the board 4073 work cohort and its linked PRs “Core Team Owned”; retain separate repository ownership groups.
- This terminology change preserves cohort filters, measurements and visible association coverage gaps.
- Greater-org benchmark: rest of AISTUDIO, excluding board 4073; confirmed by the user.
- Time and PR charts include only Jiras Done at the cutoff, with completion events during the study window.
- PR charts use direct associations to those Done Jiras; dependency links remain ownership context.
- Done includes every resolution. Reaching Done is not evidence that code shipped.
- Done-rate denominator: all selected issue types created during the study year, including tickets not yet Done.
- Done-rate numerator includes tickets that reached Done and were subsequently reopened; show that subgroup separately.
- Percentages use each chart's measured sample; zero/missing denominators are unavailable rather than zero percent.
- Board 4073: current saved filter, applied retrospectively.
- Window: November 16, 2025 through the November 16, 2026 collection snapshot.
- Preserve full lifetime history for tickets carried into the window.
- Core repos: ai-studio, ai-ui, ai-canvas-ui, ai-splunk-terraform.
- User confirmed historical ai-studio-ui and aispg-splunk-terraform were also Core-owned on November 16, 2026.
- Groups: Core-owned only; Core-owned and external; externally owned only.
- Keep repository count separate from ownership group.
- Ownership history and historical board-filter changes are unverified.

## Measures
- Time bands end at 1, 2, 4, 8, 16, then advance linearly: 32, 48, 64, 80…
- Keep every tail band and its labels accessible through horizontal scrolling; retain all outliers.
- Replace aggregate timing tables and stage tiles with histograms; keep individual evidence durations as numbers.
- Counts and percentages label each board bar, including the first two; every time-band boundary is labeled.
- Percentage overlays compare board 4073 with the rest of AISTUDIO using each cohort's measured sample denominator.
- Ownership comparisons share time bands and percentage scales; sample sizes remain visible for unequal cohorts.
- Separate completed durations from open age and unanswered review rounds; do not turn missing values into zero.
- Jira elapsed time in each status, including repeat visits, blocked time and QA.
- Creation-to-Done and first-In-Progress-to-Done; report reopened work explicitly.
- PR opening-to-merge; show closed-unmerged outcomes separately.
- Human review request-to-response by round; exclude bots and leave unmatched rounds unmeasured.
- Repository distribution; distinguish original PRs from release ports.
- Ownership comparisons need sample sizes and ticket/PR drilldowns.
- Multiple linked repositories indicate coordination, not proven blocking dependencies.

## Delivery and verification
1. Coverage audit: reconcile paginated sources, deduplicate IDs, expose unlinked tickets.
2. Metric reconstruction: verify repeated states, missing timestamps and review re-requests.
3. Dashboard: reconcile charts with filtered source rows and test links and controls.

## First slice
- High complexity; maximum 200 handwritten changed lines including tests and this plan.
- Collect current board issues, complete status history and Jira-key PR search results.
- Search Cisco organizations using their respective authenticated GitHub accounts.
- Search-body matches are candidates; title keys and explicit Jira URLs are stronger evidence.
- Missing links stay outside ownership comparisons; they are not a fourth ownership group.
- Generated evidence is local and contains no authentication credentials.
- Remote-link and complete Jira-comment discovery require a separate completeness check.

## Progress
- Jira collection passed: 3,630 unique issues; 10,433 status-change records; no history-chain mismatches.
- Timing reconstruction passed carried-in, reopened, repeated-review and malformed-history checks.
- GitHub searches use single date ranges; repeated date qualifiers are ignored by GitHub search.
- PR timelines and observable review rounds collected; each implementation slice was limited to 200 handwritten changed lines.
- Review rounds measure first human response after a request, not active reading time or every required reviewer's response.
- Local dashboard snapshot: maximum 200 handwritten lines per slice; validate filters against source rows.
- Design: time histograms, shared-axis ownership distributions, repository count bars, and linked evidence rows.
- Palette: paper #F3F7FB, ink #172E46, blue #146A96, rule #D6E1EA, amber #A56618.
- Typography: local Avenir Next for interface and Calibri fallback; left-aligned labels and tabular numbers.
- Avoid decorative metric cards: prioritize measured workflow stages and directly comparable ownership rows.
- Follow explicit blocked-by/depends-on links one hop to discover prerequisite PRs; preserve the dependency role separately.
- Dependency links without discovered prerequisite PRs remain visible gaps; neither timing nor causation is inferred from them.

## Snapshot delivered
- 3,630 Jira candidates; 10,433 status changes; no status-history chain mismatches.
- 1,449 board tickets have observed PR associations; 2,181 have no confirmed association.
- Board evidence contains 2,396 accessible PR timelines; two explicitly linked PRs remain inaccessible.
- 101 board tickets have explicit prerequisites; 73 lack discovered PRs for at least one prerequisite.
- Default types: Story, Bug, Task; 2,325 board Jiras and 8,353 rest-of-AISTUDIO Jiras qualify as Done.
- Org extraction: 26,956 candidate Jiras, including 23,326 outside board 4073; complete status histories have no chain mismatches.
- The default created-in-year Done-rate cohorts contain 2,123 board Jiras and 12,032 rest-of-AISTUDIO Jiras.
- Validation: 36 unit checks and ten browser/data checks cover percentages, early bands, linear tails and Done-only cohorts.
- Desktop and mobile layouts passed; validation browser cleanup was explicitly verified.
- Each implementation slice stayed below 200 changed handwritten lines and was checked before continuing.
- Production refresh, exhaustive link recovery and adjusted ownership comparisons remain later delivery work.
