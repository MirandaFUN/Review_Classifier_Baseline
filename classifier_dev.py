"""Dev-only baseline runner. Python 3.10+, standard library only."""
import argparse
import csv
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
LABELS = {'Violation', 'Non-violation'}

def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def write_csv(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)

def parse_prediction(raw):
    text = raw.strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.I)
        text = re.sub(r'\s*```$', '', text)
    obj = json.loads(text)
    if not isinstance(obj, dict) or obj.get('label') not in LABELS:
        raise ValueError('Invalid label or JSON structure')
    if not isinstance(obj.get('reason'), str) or not obj['reason'].strip():
        raise ValueError('Missing explanation')
    return obj

def request_payload(provider, model, prompt, review, temperature=None):
    # No labels, difficulty, source, IDs, notes or prior examples go to the model.
    message = json.dumps({'review': review}, ensure_ascii=False)
    if provider == 'anthropic':
        body = {'model': model, 'max_tokens': 512, 'system': prompt,
                'messages': [{'role': 'user', 'content': message}]}
    else:
        body = {'model': model, 'messages': [
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': message}]}
    if temperature is not None:
        body['temperature'] = temperature
    return body

def call_api(provider, endpoint, key, body):
    headers = {'Content-Type': 'application/json'}
    if provider == 'anthropic':
        headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
    else:
        headers['Authorization'] = 'Bearer ' + key
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers=headers)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                result = json.load(response)
            break
        except urllib.error.HTTPError as e:
            # Do not echo server responses that might contain request details.
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError('API HTTP ' + str(e.code)) from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise RuntimeError('API network error or timeout') from None
            time.sleep(2 ** (attempt + 1))
    if provider == 'anthropic':
        raw = ''.join(b.get('text', '') for b in result.get('content', []) if b.get('type') == 'text')
    else:
        raw = result['choices'][0]['message'].get('content') or ''
    return raw, result

def evaluate(data, records, directory):
    latest = {r['id']: r for r in records}
    joined = []
    for item in data:
        rec = latest.get(item['id'], {})
        pred = rec.get('prediction', '') if rec.get('status') == 'ok' else ''
        gold = item['label']
        kind = ('TP' if gold == 'Violation' else 'TN') if pred == gold else (
            'FN' if gold == 'Violation' else 'FP') if pred else 'Unscored'
        joined.append({**item, 'prediction': pred, 'reason': rec.get('reason', ''),
                       'outcome': kind, 'status': rec.get('status', 'not_run'),
                       'error': rec.get('error', '')})
    fields = ['id', 'original_row', 'review', 'label', 'difficulty', 'prediction',
              'reason', 'outcome', 'status', 'error', 'source']
    write_csv(directory / 'dev_results.csv', joined, fields)
    errors = [r for r in joined if r['outcome'] in ('FP', 'FN', 'Unscored')]
    for r in errors:
        r.update({'teammate_analysis': '', 'policy_or_model_issue': '', 'suggested_change': ''})
    write_csv(directory / 'errors_for_team.csv', errors,
              fields + ['teammate_analysis', 'policy_or_model_issue', 'suggested_change'])
    def summarize(rows):
        counts = {k: sum(r['outcome'] == k for r in rows) for k in ['TP', 'FP', 'FN', 'TN']}
        tp, fp, fn, tn = (counts[k] for k in ['TP', 'FP', 'FN', 'TN'])
        n = tp + fp + fn + tn
        return {**counts, 'total': len(rows), 'scored': n, 'unscored': len(rows)-n,
                'coverage': n/len(rows) if rows else None,
                'precision': tp/(tp+fp) if tp+fp else None,
                'recall': tp/(tp+fn) if tp+fn else None,
                'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                'accuracy': (tp+tn)/n if n else None}
    m = {'positive_label': 'Violation', 'overall': summarize(joined),
         'clear': summarize([r for r in joined if r['difficulty'] != 'Edge case']),
         'edge': summarize([r for r in joined if r['difficulty'] == 'Edge case'])}
    (directory/'metrics.json').write_text(json.dumps(m, indent=2), encoding='utf-8')
    s = m['overall']
    fmt = lambda v: 'undefined' if v is None else f'{v:.1%}'
    lines = ['# Baseline Dev evaluation', '', f"Scored: {s['scored']}/{s['total']}. Unscored: {s['unscored']}.",
             'Metrics below use successful predictions only. Resolve unscored rows before comparing runs.', '',
             '| | Actual Violation | Actual Non-violation |', '|---|---:|---:|',
             f"| Predicted Violation | {s['TP']} | {s['FP']} |",
             f"| Predicted Non-violation | {s['FN']} | {s['TN']} |", '',
             '| Group | Scored | Precision | Recall | F1 | Accuracy |', '|---|---:|---:|---:|---:|---:|']
    for group in ['overall', 'clear', 'edge']:
        q=m[group];lines.append(f"| {group} | {q['scored']}/{q['total']} | {fmt(q['precision'])} | {fmt(q['recall'])} | {fmt(q['f1'])} | {fmt(q['accuracy'])} |")
    lines += ['', 'These are development results, not held-out performance. Small counts and repeated prompt tuning limit generalization.',
              'Share errors_for_team.csv, dev_results.csv, run_config.json and prompt_used.txt with teammates.',
              'Use only review text for classification. Do not add test examples while revising the prompt.']
    (directory/'evaluation.md').write_text('\n'.join(lines), encoding='utf-8')
    return s

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--provider', choices=['openai', 'anthropic', 'compatible'])
    ap.add_argument('--model')
    ap.add_argument('--endpoint', help='Full chat/completions URL for compatible provider')
    ap.add_argument('--temperature', type=float, default=None)
    ap.add_argument('--run', default='baseline_v0')
    ap.add_argument('--limit', type=int, help='Connectivity check only; resume same run without limit')
    ap.add_argument('--dry-run', action='store_true', help='Validate input without API calls or fabricated predictions')
    args = ap.parse_args()
    data_path = ROOT/'dev.csv'
    data = list(csv.DictReader(data_path.open(encoding='utf-8-sig', newline='')))
    if len(data) != 81 or len({r['id'] for r in data}) != 81:
        raise SystemExit('Expected the fixed 81-row Dev dataset with unique IDs.')
    if any(r['label'] not in LABELS or not r['review'].strip() for r in data):
        raise SystemExit('Invalid Dev row.')
    prompt = (ROOT/'baseline_prompt.txt').read_text(encoding='utf-8').replace(
        '{{POLICY}}', (ROOT/'policy.txt').read_text(encoding='utf-8'))
    if args.dry_run:
        print('Validated: 81 Dev rows, 36 Violation, 45 Non-violation, 17 Edge cases.')
        print('Request fields: policy + review only. No API calls made. No Test data included.')
        return
    provider = args.provider or input('Provider (openai / anthropic / compatible): ').strip()
    if provider not in ('openai','anthropic','compatible'):
        raise SystemExit('Unsupported provider')
    model = args.model or input('Exact API model ID from your provider: ').strip()
    if not model:
        raise SystemExit('Model ID is required.')
    endpoint = args.endpoint or {'openai':'https://api.openai.com/v1/chat/completions',
                               'anthropic':'https://api.anthropic.com/v1/messages'}.get(provider)
    if not endpoint:
        endpoint = input('Full HTTPS chat/completions endpoint: ').strip()
    if not endpoint.startswith('https://'):
        raise SystemExit('Use an HTTPS API endpoint.')
    if Path(args.run).name != args.run:
        raise SystemExit('Run name must be a simple folder name.')
    directory = ROOT/'runs'/args.run
    directory.mkdir(parents=True, exist_ok=True)
    cfg = {'version':'baseline_v0', 'provider':provider, 'model':model, 'endpoint':endpoint,
           'temperature':args.temperature, 'prompt_sha256':sha(prompt),
           'dev_sha256':sha(data_path.read_text(encoding='utf-8-sig')),
           'api_max_tokens':512 if provider=='anthropic' else 'provider default',
           'anthropic_version':'2023-06-01' if provider=='anthropic' else None}
    config_file = directory/'run_config.json'
    if config_file.exists():
        old=json.loads(config_file.read_text(encoding='utf-8'))
        if any(old.get(k)!=v for k,v in cfg.items()):
            raise SystemExit('Run configuration changed. Use a new --run name instead of mixing results.')
    else:
        config_file.write_text(json.dumps({**cfg,'started_utc':datetime.now(timezone.utc).isoformat()},indent=2),encoding='utf-8')
        (directory/'prompt_used.txt').write_text(prompt,encoding='utf-8')
    raw_path=directory/'raw_responses.jsonl'
    records=[json.loads(line) for line in raw_path.read_text(encoding='utf-8').splitlines() if line.strip()] if raw_path.exists() else []
    done={r['id'] for r in records if r['status']=='ok'}
    pending=[r for r in data if r['id'] not in done]
    if args.limit is not None:
        if args.limit < 1:raise SystemExit('--limit must be positive')
        pending=pending[:args.limit]
    if not pending:
        print(evaluate(data,records,directory));return
    env={'openai':'OPENAI_API_KEY','anthropic':'ANTHROPIC_API_KEY','compatible':'LLM_API_KEY'}[provider]
    key=os.environ.get(env) or getpass.getpass(env+' (hidden, not saved): ')
    if not key:raise SystemExit('API key is required. Do not paste it into chat or source files.')
    print(f'Running {len(pending)} requests. One independent request per review. Output: {directory}')
    try:
        for index,item in enumerate(pending,1):
            rec={'id':item['id'],'utc':datetime.now(timezone.utc).isoformat(),'status':'error'}
            try:
                body=request_payload(provider,model,prompt,item['review'],args.temperature)
                raw,response=call_api(provider,endpoint,key,body)
                rec.update({'raw_text':raw,'response':response})
                obj=parse_prediction(raw)
                rec.update({'status':'ok','prediction':obj['label'],'reason':obj['reason']})
            except Exception as e:
                rec['error']=str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__
            with raw_path.open('a',encoding='utf-8') as f:
                f.write(json.dumps(rec,ensure_ascii=False)+'\n')
            records.append(rec)
            print(f"{index}/{len(pending)} {item['id']}: {rec['status']}")
            evaluate(data,records,directory)
            if rec.get('error','').startswith(('API HTTP 400','API HTTP 401','API HTTP 403','API HTTP 404')):
                print('Stopped: check model ID, API key, endpoint or parameter support before resuming.');break
            time.sleep(.25)
    finally:
        stats=evaluate(data,records,directory)
        print(json.dumps(stats,indent=2))
        print('Saved. Failed or unprocessed rows remain Unscored; rerun the same command to resume.')

if __name__=='__main__':
    main()
