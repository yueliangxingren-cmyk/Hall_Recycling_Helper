"""Run the fixed 30-case suite through /ask; live mode fails on LLM fallback."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient
from app import create_app
from providers import ModelProvider, Settings


def check_answer(case, result, live):
    fields = ('status', 'matched_item', 'bin', 'prep_step', 'source_url', 'date_checked', 'retrieval_method')
    checks = {field: result.get(field) == case['expected_' + field] for field in fields}
    if case['expected_status'] == 'ok':
        item = case['expected_matched_item']
        allowed = [f'Rule found for "{item}".', f'Published guidance for "{item}".',
                   f'For "{item}": {case["expected_bin"]} Preparation: {case["expected_prep_step"]}']
        checks['message'] = result.get('message') in allowed
        checks['grounding'] = result.get('grounding') in ('llm', 'published_rule')
    else:
        from app import NOT_COVERED_MESSAGE, REFUSED_MESSAGE
        checks['message'] = result.get('message') == (REFUSED_MESSAGE if case['expected_status'] == 'refused' else NOT_COVERED_MESSAGE)
        checks['grounding'] = result.get('grounding') == 'not_applicable'
    quality_pass = all(checks.values())
    if live and case['expected_status'] == 'ok':
        checks['live_llm'] = result.get('grounding') == 'llm'
    return quality_pass, checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, default=ROOT / 'tests.csv')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    with args.cases.open(newline='', encoding='utf-8') as stream:
        cases = list(csv.DictReader(stream))
    if len(cases) != 30 or len({c['id'] for c in cases}) != 30:
        parser.error('Expected exactly 30 uniquely identified cases')
    settings = Settings() if args.offline else Settings.from_env()
    provider = ModelProvider(settings)
    if not args.offline and not provider.chat_enabled:
        parser.error('Live evaluation requires configured chat credentials, URL and model')
    if args.output.exists():
        parser.error('Output already exists; use a new filename to preserve evidence')
    record = {
        'started_at_utc': datetime.now(timezone.utc).isoformat(),
        'mode': 'offline' if args.offline else 'live', 'transport': 'FastAPI TestClient (in process)',
        'python': platform.python_version(),
        'dependencies': {name: version(name) for name in ('fastapi','uvicorn','python-dotenv','pydantic','httpx')},
        'chat_model': settings.llm_model, 'embeddings_configured': provider.embeddings_enabled,
        'embedding_model': settings.embedding_model,
        'git_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        'sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                   for name in ('tests.csv','rules.json','app.py','providers.py','retrieval.py','grounding.py','scripts/evaluate.py','requirements.txt','requirements-dev.txt')},
        'results': [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with TestClient(create_app(provider)) as client:
        for case in cases:
            start = time.perf_counter()
            response = client.post('/ask', json={'item':case['item'], 'context':case['context']})
            result = response.json()
            quality, checks = check_answer(case, result, not args.offline)
            checks['http_200'] = response.status_code == 200
            row = {'id':case['id'], 'category':case['category'], 'item':case['item'], 'context':case['context'],
                   'seconds':round(time.perf_counter()-start, 3), 'response':result,
                   'checks':checks, 'quality_pass':quality and checks['http_200'], 'passed':all(checks.values())}
            record['results'].append(row)
            args.output.write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n')
            print(f'{case["id"]}: {"PASS" if row["passed"] else "FAIL"} ({row["seconds"]}s)', flush=True)
    record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    record['summary'] = {'total':len(cases), 'passed':sum(r['passed'] for r in record['results']),
                         'quality_passed':sum(r['quality_pass'] for r in record['results']),
                         'live_llm_answers':sum(r['response'].get('grounding') == 'llm' for r in record['results'])}
    args.output.write_text(json.dumps(record, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps(record['summary']))
    return int(record['summary']['passed'] != len(cases))


if __name__ == '__main__':
    sys.exit(main())
