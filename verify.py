"""Reconcile local source rows and exercise the dashboard in isolated Chromium."""
import json
from playwright.sync_api import sync_playwright
from audit import DATA, save
from metrics import timestamp


def verify():
    data = json.loads((DATA / 'metrics.json').read_text())
    jira = json.loads((DATA / 'jira.json').read_text())
    histories = json.loads((DATA / 'histories.json').read_text())
    issues, prs = data['issues'], data['prs']
    org = json.loads((DATA / 'org-metrics.json').read_text())
    board_keys = {r['key'] for r in issues}
    rest = [r for r in org['issues'] if r['key'] not in board_keys]
    assert not any(r['history_errors'] for r in org['issues'])
    assert org['snapshot'] == data['snapshot']
    assert len({r['key'] for r in issues}) == len(issues) == len(histories)
    assert len({r['url'] for r in prs}) == len(prs)
    assert not any(r['history_errors'] for r in issues)
    assert all(p['review_rounds'] is not None for p in prs)
    assert all(p['merge_days'] is None or p['merge_days'] >= 0 for p in prs)
    assert all(r['response_hours'] is None or r['response_hours'] >= 0 for p in prs for r in p['review_rounds'])
    assert all(not p['merged_at'] or timestamp(p['merged_at']) <= timestamp(data['snapshot']) for p in prs)
    for organization in ['cisco-aispg', 'cisco-sbg']:
        source = json.loads((DATA / (organization + '.json')).read_text())
        assert all(w['expected'] == w['received'] for w in source['windows'])
        assert sum(w['received'] for w in source['windows']) == len(source['prs'])
    raw = {r['key']: r for r in jira['issues']}
    for r in issues:
        assert abs(sum(r['state_days'].values()) - r['age_days']) < 1e-7
        f = raw[r['key']]['fields']
        assert r['open'] == (f['status']['statusCategory']['key'] != 'done')
    primary = [r for r in issues if r['type'] in {'Story', 'Bug', 'Task'}]
    done = lambda r: r['completed_in_window'] and not r['open'] and not r['history_errors']
    completed = [r for r in primary if done(r)]
    org_primary = [r for r in rest if r['type'] in {'Story','Bug','Task'}]
    org_completed = [r for r in org_primary if done(r)]
    errors, checks, requests = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width':1440, 'height':1080})
        assert not context.pages
        page = context.new_page()
        try:
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.on('request', lambda r: requests.append(r.url))
            page.goto((DATA / 'dashboard.html').as_uri())
            assert 'Jira-to-PR links' in page.locator('#introduction').inner_text()
            assert 'Core Team Owned' in page.locator('#completionBars').inner_text()
            for chart in page.locator('.histogram figcaption').all():
                assert 'Core Team Owned' in chart.text_content() and 'board 4073' not in chart.text_content()
            assert 'Board count' not in page.locator('main').inner_text()
            assert 'Core Team Owned PR count' in page.locator('#outcomes thead').inner_text()
            checks.append('introduction and Core Team Owned chart labels render without changing cohorts')
            assert page.locator('#tickets tbody tr').count() == min(150, len(completed))
            rate_rows = page.locator('.completion-row').evaluate_all('(rs)=>rs.map(r=>({...r.dataset}))')
            for source, rate in zip([primary,org_primary],rate_rows):
                born = [r for r in source if timestamp(data['start']) <= timestamp(r['created_at']) <= timestamp(data['snapshot'])]
                assert int(rate['total']) == len(born)
                assert int(rate['reached']) == sum(r['reached_done'] for r in born)
                assert int(rate['done']) + int(rate['reopened']) + int(rate['notDone']) == len(born)
            checks.append('Done rates reconcile with all created tickets, including unfinished and reopened work')
            assert page.locator('#comparison .histogram').count() == 3
            assert page.locator('#milestones .histogram').count() == 5
            checks.append('default cohort and all three ownership groups render')
            def check_histograms():
                charts = page.locator('.histogram').evaluate_all('(fs)=>fs.map(f=>({n:Number(f.dataset.sampleCount),counts:JSON.parse(f.dataset.counts),edges:JSON.parse(f.dataset.edges),p:JSON.parse(f.dataset.percentages),rn:Number(f.dataset.referenceCount),rc:JSON.parse(f.dataset.referenceCounts),rp:JSON.parse(f.dataset.referencePercentages)}))')
                for chart in charts:
                    assert sum(chart['counts']) == chart['n']
                    assert all(isinstance(n, int) and n >= 0 for n in chart['counts'])
                    if chart['counts']:
                        edges = chart['edges']
                        assert len(edges) == len(chart['counts']) + 1
                        assert edges[:6] == [0,1,2,4,8,16]
                        assert all(b - a == 16 for a,b in zip(edges[5:],edges[6:]))
                    assert sum(chart['rc']) == chart['rn']
                    for n, percentages in [(chart['n'],chart['p']),(chart['rn'],chart['rp'])]:
                        assert abs(sum(percentages)-100) < 1e-8 if n else all(v is None for v in percentages)
                for figure in page.locator('.histogram').all():
                    if int(figure.get_attribute('data-sample-count')) and len(json.loads(figure.get_attribute('data-counts'))) >= 2:
                        for i in [0,1]:
                            assert figure.locator(f'[data-count-label="{i}"]').count() == 1
                            assert '%' in figure.locator(f'[data-percent-label="{i}"]').text_content()
            check_histograms()
            for metric in ['lead', 'cycle', 'merge', 'review']:
                page.select_option('#compareMetric', metric)
                edges = page.locator('#comparison .histogram').evaluate_all('(fs)=>fs.map(f=>f.dataset.edges)')
                assert len(set(edges)) == 1
                scales = page.locator('#comparison .histogram').evaluate_all('(fs)=>fs.map(f=>f.dataset.scaleMaximum)')
                assert len(set(scales)) == 1
                check_histograms()
            page.select_option('#compareMetric', 'lead')
            for metric in ['merge', 'close', 'review']:
                page.select_option('#prMetric', metric)
                scales = page.locator('#prOwners .histogram').evaluate_all('(fs)=>fs.map(f=>f.dataset.scaleMaximum)')
                assert len(set(scales)) == 1
                check_histograms()
            page.select_option('#prMetric', 'merge')
            checks.append('histogram counts, percentages, first-two-bar labels and linear tail bands reconcile')
            for group in ['Core-owned only', 'Core-owned and external', 'Externally owned only']:
                page.select_option('#owner', group)
                expected = sum(r['ownership'] == group for r in completed)
                assert page.locator('#totals').inner_text().startswith(f'{expected:,} Done tickets selected')
                check_histograms()
            checks.append('ownership filters reconcile with evidence rows')
            page.select_option('#owner', 'all')
            for mode in ['all', 'exclude', 'only']:
                page.select_option('#ports', mode)
                urls = {u for r in completed for u in r['direct_pr_urls']}
                expected = [r for r in prs if r['url'] in urls and timestamp(data['start']) <= timestamp(r['created_at']) <= timestamp(data['snapshot'])
                            and (mode == 'all' or r['is_port'] == (mode == 'only'))]
                counts = page.locator('#repoTable tbody tr').evaluate_all('(rs)=>rs.map(r=>Number(r.cells[1].textContent))')
                assert sum(counts) == len(expected)
                if mode == 'all':
                    n_merged = page.locator('#prTimes .histogram').first.get_attribute('data-sample-count')
                    assert int(n_merged) == sum(p['outcome'] == 'Merged' for p in expected)
                    n_reviews = page.locator('#reviewHistogram .histogram').get_attribute('data-sample-count')
                    assert int(n_reviews) == sum(r['response_hours'] is not None for p in expected for r in p['review_rounds'])
                    org_urls = {u for r in org_completed for u in r['direct_pr_urls']}
                    org_expected = [p for p in org['prs'] if p['url'] in org_urls and timestamp(data['start']) <= timestamp(p['created_at']) <= timestamp(data['snapshot'])]
                    reference = page.locator('#prTimes .histogram').first.get_attribute('data-reference-count')
                    assert int(reference) == sum(p['outcome']=='Merged' for p in org_expected)
                check_histograms()
            checks.append('repository counts and port filters reconcile')
            page.select_option('#ports', 'all')
            page.fill('#search', 'AISTUDIO-28451')
            assert page.locator('#tickets tbody tr').count() == 1
            row = next(r for r in issues if r['key'] == 'AISTUDIO-28451')
            assert raw[row['key']]['fields']['resolutiondate'] is None
            assert row['done_at'] and row['completed_in_window']
            checks.append('closed Jira with missing resolution date remains measurable')
            pr_rounds = {p['url'] for p in prs if p['review_rounds']}
            example = next(r for r in completed if any(url in pr_rounds for url in r['direct_pr_urls']))
            page.fill('#search', example['key'])
            page.locator('#tickets details').first.locator('summary').click()
            assert page.locator('#tickets li').count() > 0
            assert 'Round 1: requested' in page.locator('#tickets').inner_text()
            checks.append('per-PR review-round timestamps and durations render')
            page.fill('#search', '__missing__<script>alert(1)</script>')
            assert page.locator('#tickets tbody tr').count() == 0
            assert page.locator('#tickets script').count() == 0
            page.fill('#search', '')
            page.evaluate('document.activeElement.blur(); window.scrollTo(0, 0)')
            page.screenshot(path=str(DATA / 'dashboard-preview.png'))
            page.locator('#milestones .histogram').first.screenshot(path=str(DATA / 'histogram-preview.png'))
            page.set_viewport_size({'width':390, 'height':844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.evaluate('window.scrollTo(0, 0)')
            page.screenshot(path=str(DATA / 'dashboard-mobile.png'))
            checks.append('desktop/mobile rendering and unmatched search pass')
            assert not errors
            assert all(url.startswith('file:') for url in requests)
            checks.append('no JavaScript errors or external network requests')
        finally:
            page.close()
            assert page.is_closed() and not context.pages
            context.close()
            browser.close()
            assert not browser.is_connected()
    checks.append('isolated browser pages and process explicitly closed')
    result = {'checks': checks, 'issues': len(issues), 'prs': len(prs), 'status_changes': sum(map(len, histories.values())),
              'coverage': data['coverage'], 'org_issues':len(rest), 'org_done_primary':len(org_completed),
              'browser_cleanup_verified': True, 'page_errors': errors}
    save('validation.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    verify()
