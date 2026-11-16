"""Collect PR metadata and observable human review rounds from GitHub timelines."""
import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from audit import DATA, save
from metrics import timestamp

BOT_LOGINS = {'copilot-pull-request-reviewer', 'chatgpt-codex-connector', 'github-actions'}
EVENTS = 'REVIEW_REQUESTED_EVENT,REVIEW_REQUEST_REMOVED_EVENT,PULL_REQUEST_REVIEW,READY_FOR_REVIEW_EVENT,CONVERT_TO_DRAFT_EVENT,REVIEW_DISMISSED_EVENT,REOPENED_EVENT,CLOSED_EVENT,MERGED_EVENT'
PAGE = '''timelineItems(first:100,after:$cursor,itemTypes:[EVENTS]) { pageInfo { hasNextPage endCursor } nodes {
__typename ... on ReviewRequestedEvent { createdAt requestedReviewer { __typename ... on User { login } ... on Bot { login } ... on Team { slug } } }
... on ReviewRequestRemovedEvent { createdAt }
... on PullRequestReview { createdAt submittedAt state author { __typename login } commit { oid } }
... on ReadyForReviewEvent { createdAt } ... on ConvertToDraftEvent { createdAt }
... on ReviewDismissedEvent { createdAt } ... on ReopenedEvent { createdAt }
... on ClosedEvent { createdAt } ... on MergedEvent { createdAt }
} }'''.replace('EVENTS', EVENTS)
DETAIL = '''id url title createdAt closedAt mergedAt isDraft baseRefName headRefName additions deletions changedFiles
author { __typename login } commits { totalCount }'''


def gh(args, payload=None):
    result = subprocess.run(['gh', 'api'] + args, input=json.dumps(payload) if payload else None,
                            capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    if data.get('errors'):
        raise ValueError(data['errors'])
    return data


def human(actor):
    return bool(actor and actor.get('__typename') == 'User' and actor.get('login') not in BOT_LOGINS
                and not actor.get('login', '').endswith('[bot]'))


def rounds(pr, snapshot):
    cutoff = timestamp(snapshot)
    author = (pr.get('author') or {}).get('login')
    events = sorted(pr['events'], key=lambda e: timestamp(e.get('submittedAt') or e.get('createdAt')))
    pending, result = None, []
    for e in events:
        kind = e['__typename']
        at = e.get('submittedAt') or e.get('createdAt')
        if timestamp(at) > cutoff:
            continue
        if kind == 'ReviewRequestedEvent':
            who = e.get('requestedReviewer') or {}
            if (who.get('__typename') == 'Team' or human(who)) and pending is None:
                pending = at
        elif kind == 'PullRequestReview' and e.get('submittedAt') and human(e.get('author')) and e['author']['login'] != author:
            if pending:
                result.append({'requested_at': pending, 'responded_at': at, 'response_hours': (timestamp(at) - timestamp(pending)) / 3600,
                               'state': e['state'], 'reviewer': e['author']['login']})
                pending = None
        elif kind in {'ClosedEvent', 'MergedEvent', 'ConvertToDraftEvent', 'ReviewRequestRemovedEvent'}:
            if pending:
                result.append({'requested_at': pending, 'responded_at': None, 'ended_at': at, 'response_hours': None})
                pending = None
    if pending:
        result.append({'requested_at': pending, 'responded_at': None, 'response_hours': None})
    return result


def collect(org, metrics_file='metrics.json'):
    metrics = json.loads((DATA / metrics_file).read_text())
    path = DATA / (org + '-reviews.json')
    records = json.loads(path.read_text()) if path.exists() else {}
    for pr in records.values():
        pr['rounds'] = rounds(pr, metrics['snapshot'])
    save(org + '-reviews.json', records)
    access_path = DATA / (org + '-pr-access.json')
    access = json.loads(access_path.read_text()) if access_path.exists() else {}
    eligible = {u for r in metrics['issues'] if r['completed_in_window'] and not r['history_errors'] for u in r['direct_pr_urls']}
    belongs = lambda url: url.split('/')[3] not in {'cisco-aispg','cisco-sbg'} if org == 'other' else url.split('/')[3] == org
    wanted = {p['url']: p['node_id'] for p in metrics['prs'] if p['url'] in eligible and belongs(p['url'])}
    missing = []
    for url in set(metrics['unfetched_pr_urls']) & eligible:
        if not belongs(url):
            continue
        if url not in access:
            missing.append(url)
            continue
        if 'error' not in access[url]:
            wanted[access[url]['url']] = access[url]['node_id']
    def lookup(url):
        parts = url.split('/')
        try:
            d = gh([f'repos/{parts[3]}/{parts[4]}/pulls/{parts[6]}'])
            return url, {'url': d['html_url'], 'node_id': d['node_id']}
        except subprocess.CalledProcessError as exc:
            return url, {'error': exc.stderr.strip()[:300]}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for url, result in pool.map(lookup, missing):
            access[url] = result
            if 'error' not in result:
                wanted[result['url']] = result['node_id']
            save(org + '-pr-access.json', access)
    todo = [node for url, node in wanted.items() if url not in records]
    for offset in range(0, len(todo), 20):
        query = 'query($ids:[ID!]!,$cursor:String) { nodes(ids:$ids) { ... on PullRequest { ' + DETAIL + ' ' + PAGE + ' } } }'
        batch = gh(['graphql', '--input', '-'], {'query': query, 'variables': {'ids': todo[offset:offset + 20]}})
        for pr in batch['data']['nodes']:
            if pr is None:
                raise ValueError('A requested PR is inaccessible')
            page = pr.pop('timelineItems')
            pr['events'] = page['nodes']
            while page['pageInfo']['hasNextPage']:
                cursor = page['pageInfo']['endCursor']
                page = gh(['graphql', '--input', '-'], {'query': query, 'variables': {'ids': [pr['id']], 'cursor': cursor}})['data']['nodes'][0]['timelineItems']
                pr['events'].extend(page['nodes'])
            pr['rounds'] = rounds(pr, metrics['snapshot'])
            pr['is_port'] = bool(re.search(r'cherry[\s_-]*pick|back[\s_-]*port|(?:^|[^a-z])cp(?:[^a-z]|$)', pr['title'] + ' ' + pr['headRefName'], re.I))
            records[pr['url']] = pr
        save(org + '-reviews.json', records)
        print(f'{org}: {sum(url in records for url in wanted)}/{len(wanted)} eligible PR timelines', flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('org', choices=['cisco-aispg', 'cisco-sbg', 'other'])
    p.add_argument('--organization', action='store_true')
    args = p.parse_args()
    collect(args.org, 'org-metrics.json' if args.organization else 'metrics.json')
