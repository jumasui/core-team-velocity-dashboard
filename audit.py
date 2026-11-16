"""Read-only board/PR evidence collection; run jira, cisco-aispg or cisco-sbg."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
DATA = Path(os.environ.get('JIRA_PR_DATA_DIR', str(ROOT.parent / 'core-team-velocity-analysis/evidence/jira-pr-dashboard'))).expanduser()
START = '2025-11-16T08:00:00Z'
CORE = {'ai-studio', 'ai-ui', 'ai-canvas-ui', 'ai-splunk-terraform', 'ai-studio-ui', 'aispg-splunk-terraform'}


def keys(text):
    return sorted(set(re.findall(r'(?<![A-Z0-9])AISTUDIO-\d+(?!\d)', text.upper())))


def pr_urls(value):
    return sorted(set(re.findall(r'https://github\.com/[\w.-]+/[\w.-]+/pull/\d+', json.dumps(value))))


def ownership(repos):
    if not repos:
        return None
    flags = [r.split('/')[0] in {'cisco-sbg', 'cisco-aispg'} and r.rsplit('/', 1)[-1] in CORE for r in repos]
    return 'Core-owned only' if all(flags) else 'Core-owned and external' if any(flags) else 'Externally owned only'


def save(name, value):
    path = DATA / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False))


def github_query(org, lo, hi):
    dates = [datetime.fromisoformat(v.replace('Z', '+00:00')).strftime('%Y-%m-%dT%H:%M:%SZ') for v in [lo, hi]]
    return f'is:pr org:{org} AISTUDIO in:title,body updated:{dates[0]}..{dates[1]}'


def jira_client():
    path = Path(os.environ.get('JIRA_OPS_CLI', str(Path.home() / '.codex/skills/jira-ops/scripts/jira_cli.py'))).expanduser()
    spec = importlib.util.spec_from_file_location('jira_cli', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    args = argparse.Namespace(config=None, profile=None, project='AISTUDIO', base_url=None,
                              board_id=4073, issue_type_default=None, component_default=None)
    return module.JiraClient(args)


def jira():
    c = jira_client()
    board = c.request_json('GET', '/rest/agile/1.0/board/4073/configuration')
    filt = c.request_json('GET', '/rest/api/3/filter/' + board['filter']['id'])
    end = datetime.now(timezone.utc).isoformat()
    base = re.split(r'\s+ORDER BY\s+', filt['jql'], flags=re.I)[0]
    jql = f'({base}) AND created <= "2026-11-16 23:59" AND (updated >= "2025-11-16" OR statusCategory != Done) ORDER BY key ASC'
    fields = 'summary,status,resolution,resolutiondate,created,updated,issuetype,components,description,comment,issuelinks,customfield_10028'
    payload = {'jql': jql, 'fields': fields.split(','), 'maxResults': 100}
    issues, seen = {}, set()
    while True:
        d = c.request_json('POST', '/rest/api/3/search/jql', data=payload)
        for x in d['issues']:
            f = x['fields']
            comments = f.get('comment', {})
            issues[x['id']] = {'id': x['id'], 'key': x['key'], 'pr_urls': pr_urls([f.pop('description', None), comments]),
                               'comments_total': comments.get('total', 0), 'comments_loaded': len(comments.get('comments', [])),
                               'fields': {k: v for k, v in f.items() if k != 'comment'}}
        token = d.get('nextPageToken')
        if not token:
            break
        if token in seen:
            raise ValueError('Repeated Jira issue cursor')
        seen.add(token)
        payload['nextPageToken'] = token
    save('jira.json', {'snapshot': end, 'start': START, 'jql': jql, 'board': board, 'issues': list(issues.values())})
    histories = {i: [] for i in issues}
    ids = list(issues)
    for offset in range(0, len(ids), 500):
        payload = {'issueIdsOrKeys': ids[offset:offset + 500], 'fieldIds': ['status'], 'maxResults': 1000}
        seen = set()
        while True:
            d = c.request_json('POST', '/rest/api/3/changelog/bulkfetch', data=payload)
            for group in d.get('issueChangeLogs', []):
                histories[group['issueId']].extend({k: h[k] for k in ['id', 'created', 'items']} for h in group['changeHistories'])
            token = d.get('nextPageToken')
            if not token:
                break
            if token in seen:
                raise ValueError('Repeated Jira history cursor')
            seen.add(token)
            payload['nextPageToken'] = token
        save('histories.json', histories)
        print(f'Jira histories {min(offset + 500, len(ids))}/{len(ids)}', flush=True)


def github(org):
    path = DATA / 'jira.json'
    end = json.loads(path.read_text())['snapshot']
    found, windows = {}, []

    def search(lo, hi):
        query = github_query(org, lo, hi)
        page, rows = 1, []
        while True:
            cache = hashlib.sha256(f'{query}:{page}'.encode()).hexdigest() + '.json'
            cached = DATA / 'search-cache' / cache
            if cached.exists():
                d = json.loads(cached.read_text())
            else:
                args = ['gh', 'api', '-X', 'GET', 'search/issues', '-f', 'q=' + query, '-f', 'per_page=100', '-f', f'page={page}']
                d = json.loads(subprocess.check_output(args, text=True))
                d['items'] = [{k: x.get(k) for k in ['id', 'node_id', 'html_url', 'title', 'body', 'created_at', 'closed_at', 'updated_at', 'pull_request', 'state', 'draft']} for x in d['items']]
                save('search-cache/' + cache, d)
                time.sleep(2.1)
            if d.get('incomplete_results'):
                raise ValueError('Incomplete GitHub search; retry this window')
            if d['total_count'] > 900:
                mid = (datetime.fromisoformat(lo.replace('Z', '+00:00')) + (datetime.fromisoformat(hi.replace('Z', '+00:00')) - datetime.fromisoformat(lo.replace('Z', '+00:00'))) / 2).isoformat()
                search(lo, mid)
                search(mid, hi)
                return
            rows.extend(d['items'])
            if len(rows) >= d['total_count']:
                break
            if not d['items']:
                raise ValueError('GitHub pagination ended early')
            page += 1
        windows.append({'query': query, 'expected': d['total_count'], 'received': len(rows)})
        found.update({x['html_url']: x for x in rows})
        save(org + '.json', {'snapshot': end, 'windows': windows, 'prs': list(found.values())})
        print(f'{org}: {len(found)} PR candidates', flush=True)
    search(START, end)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('source', choices=['jira', 'cisco-aispg', 'cisco-sbg'])
    source = p.parse_args().source
    jira() if source == 'jira' else github(source)
