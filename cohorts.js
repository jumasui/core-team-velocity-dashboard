function completedIssue(issue) {
  return issue.completed_in_window && !issue.open && !issue.history_errors.length;
}
function selectIssues(issues, {type, owner, query}) {
  return issues.filter(r => (type === 'all' || (type === 'primary' ? ['Story', 'Bug', 'Task'].includes(r.type) : r.type === type)) &&
    (owner === 'all' || r.ownership === owner) && (!query || `${r.key} ${r.summary}`.toLowerCase().includes(query)));
}
function selectPrs(prs, issues, {port, period, start, end}) {
  const urls = new Set(issues.filter(completedIssue).flatMap(r => r.direct_pr_urls));
  return prs.filter(p => urls.has(p.url) && (port === 'all' || (port === 'only' ? p.is_port === true : p.is_port === false)) &&
    (period === 'all' || (Date.parse(period === 'merged' ? p.merged_at : p.created_at) >= start && Date.parse(period === 'merged' ? p.merged_at : p.created_at) <= end)));
}
function completionCounts(issues, start, end) {
  const cohort = issues.filter(r => Date.parse(r.created_at) >= start && Date.parse(r.created_at) <= end);
  const done = cohort.filter(r => !r.open).length;
  const reopened = cohort.filter(r => r.open && r.reached_done).length;
  return {total: cohort.length, done, reopened, notDone: cohort.length - done - reopened, reached: done + reopened};
}
if (typeof module !== 'undefined') module.exports = {completedIssue, selectIssues, selectPrs, completionCounts};
