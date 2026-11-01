"""Download existing local Studio experiment records without creating human actions."""
import argparse
import hashlib
from http.cookiejar import CookieJar
import json
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, Request


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--project-id')
    parser.add_argument('--data-dir', type=Path, default=Path('.data'),
                        help='Local operator-owned application directory containing session.key')
    parser.add_argument('--output', type=Path, default=Path('research/results/application-export'))
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
        parser.error('This script only supports the trusted local loopback application')
    base = args.url.rstrip('/') + '/api/v1'
    client = build_opener(HTTPCookieProcessor(CookieJar()), NoRedirect())

    def get(path, headers=None):
        with client.open(Request(base + path, headers=headers or {}), timeout=30) as response:
            return response.read()

    if not (args.data_dir / 'session.key').is_file():
        parser.error('Start Studio first or provide --data-dir for its local operator session key')
    from oe_studio.auth import bootstrap_token
    get('/session', {'X-OE-Session-Token': bootstrap_token(args.data_dir)})
    project_id = args.project_id
    if not project_id:
        projects = json.loads(get('/projects'))['items']
        demos = [p for p in projects if p.get('domain') == 'demo']
        if len(demos) != 1:
            parser.error('Provide --project-id when there is not exactly one demo project')
        project_id = demos[0]['id']
    prefix = '/projects/' + quote(project_id, safe='') + '/experiments/export?format='
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {'schema_version': 1, 'project_id': project_id, 'files': {}}
    for format in ('json', 'csv'):
        content = get(prefix + format)
        target = args.output / ('runs.' + format)
        target.write_bytes(content)
        manifest['files'][target.name] = hashlib.sha256(content).hexdigest()
    records = json.loads((args.output / 'runs.json').read_text())
    manifest['run_count'] = len(records['items'])
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(f'Exported {manifest["run_count"]} existing runs to {args.output}')


if __name__ == '__main__':
    main()
