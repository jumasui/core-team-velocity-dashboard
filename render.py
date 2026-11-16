"""Build a self-contained local dashboard; no remote scripts or credentials."""
import json
from audit import ROOT, DATA


def embedded_json(value):
    return json.dumps(value, ensure_ascii=True).replace('<', '\\u003c').replace('&', '\\u0026')


def render():
    data = json.loads((DATA / 'metrics.json').read_text())
    data['organization'] = json.loads((DATA / 'org-metrics.json').read_text())
    template = (ROOT / 'dashboard.html').read_text()
    app = '\n'.join((ROOT / name).read_text() for name in ['cohorts.js', 'histogram.js', 'dashboard.js'])
    html = template.replace('__DATA__', embedded_json(data)).replace('__APP__', app)
    output = DATA / 'dashboard.html'
    output.write_text(html)
    print(output)


if __name__ == '__main__':
    render()
