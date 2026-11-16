"""Collect all AISTUDIO work against the original dashboard cutoff; UI excludes board 4073."""
import json
import argparse
from audit import DATA, jira_client, pr_urls, save
from metrics import timestamp, build


def collect():
    original = json.loads((DATA / 'jira.json').read_text())
    c = jira_client()
    project_statuses = c.request_json('GET', '/rest/api/3/project/AISTUDIO/statuses')
    done_ids = sorted({s['id'] for t in project_statuses for s in t['statuses'] if s['statusCategory']['key'] == 'done'})
    jql = 'project = AISTUDIO AND created <= "2026-11-16 23:59" AND (updated >= "2025-11-16" OR statusCategory != Done) ORDER BY key ASC'
    fields = 'summary,status,resolution,resolutiondate,created,updated,issuetype,components,description,comment,issuelinks'
    payload = {'jql': jql, 'fields': fields.split(','), 'maxResults': 100}
    issues, seen, page = {}, set(), 0
    while True:
        name = f'org-cache/issues-{page:04}.json'
        path = DATA / name
        if path.exists():
            d = json.loads(path.read_text())
        else:
            d = c.request_json('POST', '/rest/api/3/search/jql', data=payload)
            save(name, d)
        for x in d['issues']:
            f = x['fields']
            if timestamp(f['created']) > timestamp(original['snapshot']):
                continue
            comments = f.get('comment', {})
            issues[x['id']] = {'id': x['id'], 'key': x['key'], 'pr_urls': pr_urls([f.get('description'), comments]),
                              'comments_total': comments.get('total', 0), 'comments_loaded': len(comments.get('comments', [])),
                              'fields': {k: v for k, v in f.items() if k not in {'comment', 'description'}}}
        token = d.get('nextPageToken')
        if not token:
            break
        if token in seen:
            raise ValueError('Repeated organization issue cursor')
        seen.add(token)
        payload['nextPageToken'] = token
        page += 1
        if page % 10 == 0:
            print(f'AISTUDIO: {len(issues)} issues collected', flush=True)
    save('org-jira.json', {'snapshot': original['snapshot'], 'start': original['start'], 'jql': jql,
                           'board': original['board'], 'done_ids': done_ids, 'issues': list(issues.values())})
    histories = {i: [] for i in issues}
    ids = list(issues)
    for offset in range(0, len(ids), 500):
        payload = {'issueIdsOrKeys': ids[offset:offset + 500], 'fieldIds': ['status'], 'maxResults': 1000}
        seen, page = set(), 0
        while True:
            name = f'org-cache/history-{offset:05}-{page:03}.json'
            path = DATA / name
            d = json.loads(path.read_text()) if path.exists() else c.request_json('POST', '/rest/api/3/changelog/bulkfetch', data=payload)
            save(name, d)
            for group in d.get('issueChangeLogs', []):
                histories[group['issueId']].extend({k: h[k] for k in ['id', 'created', 'items']} for h in group['changeHistories'])
            token = d.get('nextPageToken')
            if not token:
                break
            if token in seen:
                raise ValueError('Repeated organization history cursor')
            seen.add(token)
            payload['nextPageToken'] = token
            page += 1
        save('org-histories.json', histories)
        print(f'AISTUDIO histories: {min(offset + 500, len(ids))}/{len(ids)}', flush=True)
    build('org-jira.json', 'org-histories.json', 'org-metrics.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-only', action='store_true')
    args = parser.parse_args()
    build('org-jira.json', 'org-histories.json', 'org-metrics.json') if args.build_only else collect()
