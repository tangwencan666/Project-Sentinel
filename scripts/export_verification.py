"""Publish compact measured test results; never export raw logs or machine paths."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository-audit', default='repository-audit-first.json')
    parser.add_argument('--release', choices=('original','polish','interview'), default='original')
    args = parser.parse_args()
    if Path(args.repository_audit).name != args.repository_audit:
        raise ValueError('Use an audit filename')
    hashes = {}

    def read(name):
        data = (ROOT / 'artifacts/phase5' / name).read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        return json.loads(data)

    polished=args.release!='original';interview=args.release=='interview'
    backend = read('backend-interview.json' if interview else 'backend-polish.json' if polished else 'backend-tests-final.json')
    replay = read('frontend-interview.json' if interview else 'frontend-polish-final.json' if polished else 'replay-tests-final.json')
    browser = read('browser-interview-final.json' if interview else 'browser-polish-release.json' if polished else 'browser-release.json')
    live = read('live-workspace-release.json')
    security = read('public-security-interview.json' if interview else 'public-security-polish.json' if polished else 'public-security-release.json')
    clean = read('clean-start-interview.json' if interview else 'clean-start-polish.json' if polished else 'clean-start-first.json')
    cost = read('no-live-llm-interview.json' if interview else 'no-live-llm-polish-final.json' if polished else 'no-live-llm-proof.json')
    repo = read(args.repository_audit)
    assert backend['exit_code'] == replay['exit_code'] == 0
    assert all(r['passed'] for r in (browser, live, security, clean, cost, repo))
    backend_result=re.search(r'(\d+) passed, (\d+) warning in ([\d.]+)s',backend['stdout'])
    frontend_result=re.search(r'pass (\d+)',replay['stdout'])
    assert backend_result and int(backend_result[1])==267
    assert frontend_result and int(frontend_result[1])==(17 if polished else 7)
    result = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'Local Phase 5 verification; no new live LLM benchmark. Summary, not raw logs.',
        'backend': {'passed': int(backend_result[1]), 'existing': 189, 'new_portfolio': 78, 'warnings': int(backend_result[2]),
                    'elapsed_seconds': float(backend_result[3]),
                    'trace_regression_source': 'Included genuine 90-span public recording, hash-verified; no archive-dependent skip.' if polished else 'Original internal archive; skips if absent.'},
        'replay_unit_tests': {'passed': 7},
        'frontend_unit_tests': {'passed': int(frontend_result[1]),'replay':7,'document_rendering_security':10 if polished else 0},
        'browser': {k: browser[k] for k in ('scope', 'checks', 'errors', 'resource_failures', 'mutations', 'performance', 'screenshots', 'passed')},
        'local_live_readonly': live,
        'public_security': security,
        'clean_start': {k: clean[k] for k in ('source', 'health', 'config', 'recorded_run_id', 'passed', 'cleanup_exit_code')},
        'cost': cost,
        'repository_audit': repo,
        'source_report_sha256': hashes,
        'measured_source_sha256': {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ('sentinel/public_demo.py', 'sentinel/api.py', 'web/portfolio.js',
                         'web/portfolio.css', 'web/replay.js', 'web/live.html',
                         'web/documents.js', 'web/index.html', 'tests/test_runtime_followup.py',
                         'Dockerfile.demo', 'compose.yaml', 'portfolio/data/manifest.json')
        },
    }
    if interview:
        offline=read('offline-runtime.json');dry_run=read('demo-dry-run.json')
        assert offline['passed'] and dry_run['passed']
        result['offline_runtime']=offline;result['interview_dry_run']=dry_run
    (ROOT / 'portfolio/verification.json').write_text(json.dumps(result, indent=2, ensure_ascii=True) + '\n', encoding='utf-8')
    print(json.dumps({'passed': True, 'backend': int(backend_result[1]), 'frontend': int(frontend_result[1]),
                      'browser_checks': len(browser['checks']), 'real_llm_calls': cost['phase5_real_llm_calls']}))


if __name__ == '__main__':
    main()
