"""Reconstruct elapsed state time without relying on Jira resolution dates."""
import json
from collections import defaultdict
from datetime import datetime
from audit import DATA, START, CORE, keys, ownership, save


def timestamp(value):
    if isinstance(value, (int, float)):
        return value / 1000
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def timeline(issue, history, end, done_ids):
    f = issue['fields']
    created, end = timestamp(f['created']), timestamp(end)
    changes = sorted([(timestamp(h['created']), item) for h in history for item in h['items']
                      if item['field'] == 'status'], key=lambda x: x[0])
    events, future = [e for e in changes if e[0] <= end], [e for e in changes if e[0] > end]
    expected = future[0][1]['from'] if future else f['status']['id']
    state = events[0][1]['from'] if events else expected
    initial = state
    cursor, durations, entered = created, defaultdict(float), defaultdict(list)
    entered[state].append(created)
    errors, completions, reopened = [], [], 0
    for at, item in events:
        if at < cursor or item['from'] != state:
            errors.append('inconsistent status history')
        if at < created:
            errors.append('status change before creation')
        durations[state] += max(0, at - cursor) / 86400
        if state not in done_ids and item['to'] in done_ids:
            completions.append(at)
        if state in done_ids and item['to'] not in done_ids:
            reopened += 1
        cursor, state = at, item['to']
        entered[state].append(at)
    if state != expected:
        errors.append('history does not match current status')
    durations[state] += max(0, end - cursor) / 86400
    completed_at = completions[-1] if state in done_ids and completions else None
    progress = min(entered.get('3', []), default=None)
    review = min(entered.get('10083', []), default=None)
    todo = min(entered.get('10056', []) + entered.get('4', []), default=None)
    return {'key': issue['key'], 'created_at': f['created'], 'status_id': state,
            'status_name': future[0][1].get('fromString', state) if future else f['status'].get('name', state),
            'reached_done': bool(completions or initial in done_ids), 'initial_status': initial, 'state_days': dict(durations),
            'history_errors': sorted(set(errors)), 'reopened': reopened, 'done_at': completed_at,
            'lead_days': (completed_at - created) / 86400 if completed_at else None,
            'cycle_days': (completed_at - progress) / 86400 if completed_at and progress else None,
            'todo_to_progress_days': (progress - todo) / 86400 if progress and todo and progress >= todo else None,
            'progress_to_review_days': (review - progress) / 86400 if review and progress and review >= progress else None,
            'review_to_done_days': (completed_at - review) / 86400 if completed_at and review else None,
            'age_days': (end - created) / 86400, 'open': state not in done_ids}


def primary_keys(pr):
    title = keys(pr['title'])
    body = pr.get('body') or ''
    # Keep broad body mentions as candidates rather than asserted implementation links.
    return title, sorted(set(keys(body)) - set(title))


def dependencies(links):
    result = set()
    for relation in links:
        for side, direction in [('inwardIssue', 'inward'), ('outwardIssue', 'outward')]:
            if relation['type'][direction].lower() in {'is blocked by', 'blocked-by', 'depends on'} and side in relation:
                result.add(relation[side]['key'])
    return sorted(result)


def build(jira_file='jira.json', history_file='histories.json', output='metrics.json'):
    jira = json.loads((DATA / jira_file).read_text())
    histories = json.loads((DATA / history_file).read_text())
    board, issues = jira['board'], jira['issues']
    done_ids = set(jira.get('done_ids') or [s['id'] for s in board['columnConfig']['columns'][-1]['statuses']])
    prs, searches, details, aliases, failures = {}, [], {}, {}, {}
    for org in ['cisco-aispg', 'cisco-sbg', 'other']:
        path = DATA / (org + '.json')
        if path.exists():
            d = json.loads(path.read_text())
            prs.update({x['html_url']: x for x in d['prs']})
            searches.extend(d['windows'])
        review_path = DATA / (org + '-reviews.json')
        if review_path.exists():
            details.update(json.loads(review_path.read_text()))
        access_path = DATA / (org + '-pr-access.json')
        if access_path.exists():
            for source, result in json.loads(access_path.read_text()).items():
                if 'error' in result:
                    failures[source] = result['error']
                else:
                    aliases[source] = result['url']
    for url, p in details.items():
        prs[url] = {'html_url': url, 'node_id': p['id'], 'title': p['title'], 'body': (prs.get(url) or {}).get('body') or '', 'created_at': p['createdAt'],
                    'closed_at': p['closedAt'], 'pull_request': {'merged_at': p['mergedAt']}}
    by_key, candidates = defaultdict(set), defaultdict(set)
    for url, p in prs.items():
        direct, possible = primary_keys(p)
        for key in direct:
            by_key[key].add(url)
        for key in possible:
            candidates[key].add(url)
    rows = []
    for issue in issues:
        f = issue['fields']
        row = timeline(issue, histories[issue['id']], jira['snapshot'], done_ids)
        direct = {aliases.get(u, u) for u in by_key[issue['key']] | set(issue['pr_urls'])}
        blocked_by = dependencies(f.get('issuelinks', []))
        dependency_urls = {aliases.get(u, u) for key in blocked_by for u in by_key[key]}
        urls = sorted(direct | dependency_urls)
        repos = sorted({'/'.join(u.split('/')[3:5]) for u in urls})
        row.update({'summary': f['summary'], 'type': f['issuetype']['name'], 'status': row['status_name'],
                    'resolution': (f.get('resolution') or {}).get('name'), 'repos': repos, 'pr_urls': urls,
                    'candidate_pr_urls': sorted(candidates[issue['key']] - set(urls)), 'ownership': ownership(repos),
                    'completed_in_window': bool(row['done_at'] and timestamp(START) <= row['done_at']),
                    'comment_gap': issue['comments_total'] - issue['comments_loaded'], 'blocked_by_keys': blocked_by,
                    'direct_pr_urls': sorted(direct), 'dependency_pr_urls': sorted(dependency_urls),
                    'unresolved_dependency_keys': [key for key in blocked_by if not by_key[key]]})
        rows.append(row)
    linked = {u for r in rows for u in r['pr_urls']}
    pr_rows = []
    for url in sorted(linked & prs.keys()):
        p = prs[url]
        merged = (p.get('pull_request') or {}).get('merged_at')
        closed = p.get('closed_at')
        if timestamp(p['created_at']) > timestamp(jira['snapshot']):
            continue
        merged = merged if merged and timestamp(merged) <= timestamp(jira['snapshot']) else None
        closed = closed if closed and timestamp(closed) <= timestamp(jira['snapshot']) else None
        pr_rows.append({'url': url, 'node_id': p['node_id'], 'title': p['title'], 'repo': '/'.join(url.split('/')[3:5]),
                        'created_at': p['created_at'], 'merged_at': merged, 'closed_at': closed,
                        'merge_days': (timestamp(merged) - timestamp(p['created_at'])) / 86400 if merged else None,
                        'close_days': (timestamp(closed) - timestamp(p['created_at'])) / 86400 if closed else None,
                        'outcome': 'Merged' if merged else 'Closed unmerged' if closed else 'Open',
                        'ownership': ownership(['/'.join(url.split('/')[3:5])])})
        detail = details.get(url)
        pr_rows[-1].update({'review_rounds': detail['rounds'] if detail else None,
                            'is_port': detail['is_port'] if detail else None,
                            'additions': detail['additions'] if detail else None,
                            'deletions': detail['deletions'] if detail else None,
                            'changed_files': detail['changedFiles'] if detail else None})
    result = {'snapshot': jira['snapshot'], 'start': START, 'board': board, 'issues': rows, 'prs': pr_rows,
              'ownership_baseline': {'core': sorted(CORE)},
              'searches': searches, 'unfetched_pr_urls': sorted(linked - prs.keys()),
              'access_failures': {url:error for url,error in failures.items() if url in linked},
              'coverage': {'issues': len(rows), 'linked_issues': sum(bool(r['pr_urls']) for r in rows),
                           'unlinked_issues': sum(not r['pr_urls'] for r in rows),
                           'candidate_only_issues': sum(bool(r['candidate_pr_urls']) and not r['pr_urls'] for r in rows),
                           'explicit_dependency_issues': sum(bool(r['blocked_by_keys']) for r in rows),
                           'unresolved_dependency_issues': sum(bool(r['unresolved_dependency_keys']) for r in rows),
                           'history_error_issues': sum(bool(r['history_errors']) for r in rows),
                           'missing_resolution_dates': sum(x['fields']['status']['statusCategory']['key'] == 'done' and not x['fields'].get('resolutiondate') for x in issues)}}
    save(output, result)
    print(json.dumps({'coverage': result['coverage'], 'linked_prs': len(pr_rows), 'unfetched_prs': len(result['unfetched_pr_urls'])}, indent=2))


if __name__ == '__main__':
    build()
