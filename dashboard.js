const D = JSON.parse(document.querySelector('#data').textContent);
const groups = ['Core-owned only', 'Core-owned and external', 'Externally owned only'];
const start = Date.parse(D.start), end = Date.parse(D.snapshot);
const boardKeys = new Set(D.issues.map(r => r.key));
const organizationIssues = D.organization.issues.filter(r => !boardKeys.has(r.key));
const $ = id => document.getElementById(id);
function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text != null) n.textContent = String(text);
  if (cls) n.className = cls;
  return n;
}
function link(url, text) {
  const a = el('a', text);
  if (/^https:\/\/(github\.com|cisco-sbg\.atlassian\.net)\//.test(url)) a.href = url;
  return a;
}
const fmt = (v, unit = '') => v == null ? '—' : `${v.toFixed(1)}${unit}`;
function table(id, headers, rows) {
  const t = el('table'), head = el('thead'), tr = el('tr');
  headers.forEach(h => tr.append(el('th', h)));
  head.append(tr); t.append(head);
  const body = el('tbody');
  rows.forEach(row => {
    const r = el('tr');
    row.forEach(value => { const td = el('td'); td.append(value instanceof Node ? value : el('span', value)); r.append(td); });
    body.append(r);
  });
  t.append(body); $(id).classList.add('scroll'); $(id).replaceChildren(t);
}
const rounds = prs => prs.flatMap(p => p.review_rounds || []);
const share = (count, total) => total ? 100 * count / total : null;
function completionChart(board, organization) {
  $('completionBars').replaceChildren();
  const labels = ['Done at cutoff', 'Reached Done, then reopened', 'Not yet Done'];
  const colors = ['#146a96', '#a56618', '#d6e1ea'];
  const entries = [['Core Team Owned Jiras', completionCounts(board, start, end)], ['Rest of AISTUDIO', completionCounts(organization, start, end)]];
  entries.forEach(([name, c]) => {
    const row = el('div', null, 'completion-row');
    Object.assign(row.dataset, c);
    row.append(el('strong', `${name}: ${percent(share(c.reached, c.total))} reached Done (${c.reached}/${c.total})`));
    if (c.total) {
      const bar = el('div', null, 'completion-bar'); bar.setAttribute('aria-label', `${name}: ${c.reached} of ${c.total} reached Done`);
      [c.done, c.reopened, c.notDone].forEach((count, i) => {
        const segment = el('div'); Object.assign(segment.dataset, {count, denominator:c.total});
        segment.style.width = `${share(count, c.total)}%`; segment.style.background = colors[i];
        segment.title = `${labels[i]}: ${count}/${c.total} (${percent(share(count, c.total))})`; bar.append(segment);
      }); row.append(bar);
    } else row.append(el('p', 'No tickets created in the study window for these filters.'));
    $('completionBars').append(row);
  });
  table('completionStats', ['Cohort', 'Created in study year', ...labels], entries.map(([name,c]) => [name,c.total,...[c.done,c.reopened,c.notDone].map(n => `${n} (${percent(share(n,c.total))})`)]));
}
function render() {
  const query = $('search').value.trim().toLowerCase();
  const filters = {type:$('type').value, owner:$('owner').value, query};
  const selected = selectIssues(D.issues, filters), orgSelected = selectIssues(organizationIssues, filters);
  const rows = selected.filter(completedIssue), completed = rows, benchmark = orgSelected.filter(completedIssue);
  const options = {port:$('ports').value, period:$('prcohort').value, start, end};
  const prs = selectPrs(D.prs, rows, options), orgPrs = selectPrs(D.organization.prs, benchmark, options);
  completionChart(selected, orgSelected);
  $('totals').textContent = `${rows.length.toLocaleString()} Done tickets selected · ${prs.length.toLocaleString()} directly linked PRs · benchmark: ${benchmark.length.toLocaleString()} Done Jiras and ${orgPrs.length.toLocaleString()} PRs`;
  histogramGroup('flow', D.board.columnConfig.columns.filter(c => c.name !== 'Done').map(c => {
    const ids = c.statuses.map(s => s.id), vals = completed.filter(r => ids.some(id => id in r.state_days)).map(r => ids.reduce((n, id) => n + (r.state_days[id] || 0), 0));
    const reference = benchmark.filter(r => ids.some(id => id in r.state_days)).map(r => ids.reduce((n,id) => n + (r.state_days[id] || 0),0));
    return {title: `Cumulative time in ${c.name}`, values: vals, reference};
  }), 'days', 'Jiras');
  $('stageCaption').textContent = `Only Jiras Done at the cutoff, with a completion during the study year. Blue bars: Core Team Owned Jiras; amber line: rest of AISTUDIO. Percentages use measured durations within each cohort.`;
  histogramGroup('milestones', [['Creation → Done', 'lead_days'], ['In Progress → Done', 'cycle_days'], ['To Do → In Progress', 'todo_to_progress_days'], ['In Progress → Code Review', 'progress_to_review_days'], ['Code Review → Done', 'review_to_done_days']].map(([title, field]) => ({title, values: completed.map(r => r[field]), reference:benchmark.map(r => r[field])})), 'days', 'Jiras');
  const cm = $('compareMetric').value;
  const compareLabels = {lead: 'Creation → Done', cycle: 'In Progress → Done', merge: 'PR opening → merge', review: 'Human review response'};
  const prValues = (p,m) => m === 'review' ? rounds(p).map(r => r.response_hours) : p.filter(r => r.outcome === (m === 'merge' ? 'Merged' : 'Closed unmerged')).map(r => r[m === 'merge' ? 'merge_days' : 'close_days']);
  const comparisonValues = (j,p,m) => m === 'lead' || m === 'cycle' ? j.map(r => r[m === 'lead' ? 'lead_days' : 'cycle_days']) : prValues(p,m);
  histogramGroup('comparison', groups.map(g => {
    const j = completed.filter(r => r.ownership === g), groupUrls = new Set(j.flatMap(r => r.direct_pr_urls));
    const p = prs.filter(p => groupUrls.has(p.url));
    const oj = benchmark.filter(r => r.ownership === g), ou = new Set(oj.flatMap(r => r.direct_pr_urls)), op = orgPrs.filter(r => ou.has(r.url));
    return {title: `${g}: ${compareLabels[cm]}`, values:comparisonValues(j,p,cm), reference:comparisonValues(oj,op,cm)};
  }), cm === 'review' ? 'hours' : 'days', cm === 'review' ? 'review rounds' : cm === 'merge' ? 'PRs' : 'Jiras', true);
  const pm = $('prMetric').value;
  histogramGroup('prOwners', ['Core-owned only', 'Externally owned only'].map(g => {
    const p = prs.filter(p => p.ownership === g);
    return {title: `${g}: ${pm === 'review' ? 'Human review response' : pm === 'merge' ? 'Opening → merge' : 'Opening → unmerged closure'}`, values:prValues(p,pm), reference:prValues(orgPrs.filter(r => r.ownership === g),pm)};
  }), pm === 'review' ? 'hours' : 'days', pm === 'review' ? 'review rounds' : 'PRs', true);
  const counts = new Map(); prs.forEach(p => counts.set(p.repo, (counts.get(p.repo) || 0) + 1));
  const orgCounts = new Map(); orgPrs.forEach(p => orgCounts.set(p.repo, (orgCounts.get(p.repo) || 0) + 1));
  const sorted = [...new Set([...counts.keys(), ...orgCounts.keys()])].sort((a,b) => (counts.get(b)||0)-(counts.get(a)||0) || (orgCounts.get(b)||0)-(orgCounts.get(a)||0));
  table('repoTable', ['Repository', 'Core Team Owned PRs', 'Core Team Owned %', 'Org PRs', 'Org %', 'Share (0–100%)'], sorted.map(repo => {
    const count = counts.get(repo)||0, oc = orgCounts.get(repo)||0, track = el('div',null,'bartrack');
    [[count,prs.length,'#146a96'],[oc,orgPrs.length,'#a56618']].forEach(([n,total,color]) => { const bar=el('div',null,'bar'); bar.style.width=`${share(n,total)||0}%`; bar.style.background=color; track.append(bar); });
    return [link(`https://github.com/${repo}`,repo),count,percent(share(count,prs.length)),oc,percent(share(oc,orgPrs.length)),track];
  }));
  const rr = rounds(prs), measured = rr.filter(r => Number.isFinite(r.response_hours));
  histogramGroup('reviewHistogram', [{title: 'Review request → human response', values: rr.map(r => r.response_hours), reference:rounds(orgPrs).map(r => r.response_hours)}], 'hours', 'review rounds');
  const orgRounds = rounds(orgPrs), orgMeasured = orgRounds.filter(r => Number.isFinite(r.response_hours));
  const coverageRows = [['PRs with timeline evidence',prs.filter(p=>p.review_rounds!==null).length,prs.length,orgPrs.filter(p=>p.review_rounds!==null).length,orgPrs.length],['Measured requested rounds',measured.length,rr.length,orgMeasured.length,orgRounds.length],['Unanswered/interrupted rounds',rr.length-measured.length,rr.length,orgRounds.length-orgMeasured.length,orgRounds.length]];
  table('reviewSummary', ['Measure','Core Team Owned count / denominator','Core Team Owned %','Org count / denominator','Org %'],coverageRows.map(([name,n,total,on,ot])=>[name,`${n}/${total}`,percent(share(n,total)),`${on}/${ot}`,percent(share(on,ot))]));
  table('outcomes', ['PR outcome', 'Core Team Owned PR count', 'Core Team Owned %', 'Org count', 'Org %'], ['Merged', 'Closed unmerged', 'Open'].map(o => { const n=prs.filter(p=>p.outcome===o).length, on=orgPrs.filter(p=>p.outcome===o).length; return [o,n,percent(share(n,prs.length)),on,percent(share(on,orgPrs.length))]; }));
  const lifetime = (p,o) => p.filter(p=>p.outcome===o).map(p=>o==='Merged'?p.merge_days:o==='Closed unmerged'?p.close_days:(end-Date.parse(p.created_at))/86400000);
  histogramGroup('prTimes', ['Merged','Closed unmerged','Open'].map(o=>({title:o==='Merged'?'PR opening → merge':o==='Open'?'Still-open PR age (linked to Done Jiras)':'PR opening → closed without merge',values:lifetime(prs,o),reference:lifetime(orgPrs,o)})), 'days','PRs');
  const orgUrls = new Set(benchmark.flatMap(r=>r.direct_pr_urls));
  const fetched = D.organization.prs.filter(p=>orgUrls.has(p.url)).length;
  table('orgQuality',['Benchmark coverage (current filters)','Count / denominator','Percentage'],[
    ['Done Jiras with observed direct PR links',`${benchmark.filter(r=>r.direct_pr_urls.length).length}/${benchmark.length}`,percent(share(benchmark.filter(r=>r.direct_pr_urls.length).length,benchmark.length))],
    ['Associated PR URLs with fetched metadata',`${fetched}/${orgUrls.size}`,percent(share(fetched,orgUrls.size))],
    ['Selected PRs with review timelines',`${orgPrs.filter(p=>p.review_rounds!==null).length}/${orgPrs.length}`,percent(share(orgPrs.filter(p=>p.review_rounds!==null).length,orgPrs.length))]
  ]);
  const prMap = new Map(D.prs.map(p => [p.url, p]));
  table('tickets', ['Jira / evidence', 'Ownership', 'Repos', 'Lead (d)', 'Cycle (d)', 'Status'], rows.slice(0, 150).map(r => {
    const cell = el('div'); cell.append(link(`https://cisco-sbg.atlassian.net/browse/${r.key}`, r.key), el('div', r.summary));
    if (r.blocked_by_keys.length) {
      const dep = el('p', 'Blocked by / depends on: '); r.blocked_by_keys.forEach(key => { dep.append(link(`https://cisco-sbg.atlassian.net/browse/${key}`, key), document.createTextNode(' ')); }); cell.append(dep);
    }
    if (r.direct_pr_urls.length) {
      const details = el('details'); details.append(el('summary', `${r.direct_pr_urls.length} directly linked PRs`));
      r.direct_pr_urls.forEach(url => {
        const p = prMap.get(url), line = el('div'); line.append(link(url, p?.title || url));
        if (p) {
          const label = p.outcome === 'Open' ? 'open age' : p.outcome === 'Merged' ? 'opening to merge' : 'opening to closure';
          const days = p.outcome === 'Open' ? (end - Date.parse(p.created_at)) / 86400000 : p.outcome === 'Merged' ? p.merge_days : p.close_days;
          line.append(el('small', ` · ${p.outcome} · ${label}: ${fmt(days, ' d')}`));
          const sessions = el('ol');
          rounds([p]).forEach((rr, i) => {
            const date = value => new Date(value).toLocaleString('en-US', {timeZone:'America/Los_Angeles'});
            sessions.append(el('li', `Round ${i + 1}: requested ${date(rr.requested_at)} Pacific; ${rr.responded_at ? `responded ${date(rr.responded_at)} Pacific (${fmt(rr.response_hours, ' h')})` : 'unanswered or interrupted; duration unmeasured'}`));
          });
          if (sessions.childNodes.length) line.append(sessions);
        }
        details.append(line);
      });
      cell.append(details);
    }
    return [cell, r.ownership || 'Unclassified; outside comparison', r.repos.join(', '), fmt(r.lead_days), fmt(r.cycle_days), r.status];
  }));
}
$('scope').textContent = `Core Team Owned · Jira board 4073 · ${new Date(D.start).toLocaleDateString('en-US', {timeZone:'America/Los_Angeles'})}–${new Date(D.snapshot).toLocaleString('en-US', {timeZone:'America/Los_Angeles'})} Pacific · Source: Jira and GitHub API snapshots`;
table('quality', ['Coverage check', 'Full collection'], Object.entries(D.coverage).map(([k, v]) => [k.replaceAll('_', ' '), v]));
const caveat = el('p', `${D.unfetched_pr_urls.length} observed PR URLs lack fetched metadata; ${Object.keys(D.access_failures).length} access failures. ${D.issues.filter(r => r.comment_gap > 0).length} tickets have truncated comment collections. All ownership classifications use observed associations and can change as links are recovered.`, 'notice'); $('quality').append(caveat);
$('quality').append(el('p', `Core ownership baseline: ${D.ownership_baseline.core.join(', ')}. The historical ai-studio-ui and aispg-splunk-terraform names were confirmed Core-owned by the user.`));
['type', 'owner', 'prcohort', 'ports', 'compareMetric', 'prMetric'].forEach(id => $(id).addEventListener('change', render));
$('search').addEventListener('input', render);
render();
