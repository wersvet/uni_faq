"""Isolated-process benchmarking. Test results are reported after dev calibration."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import uuid
from datetime import datetime,timezone
import numpy as np
from faq.config import ROOT,DATA
from faq.database import connect,load_documents,sync_cases
from faq.retrieval import SearchEngine


def load_cases():return [json.loads(line) for line in (DATA/'evaluation.jsonl').read_text().splitlines() if line.strip()]


def metrics(rows):
    return dict(p1=float(np.mean([r['p1'] for r in rows])),p3=float(np.mean([r['p3'] for r in rows])),mrr=float(np.mean([r['mrr'] for r in rows])),hit3=float(np.mean([r['hit3'] for r in rows])),latency_ms=float(np.mean([r['latency_ms'] for r in rows])))


def score_hits(ids,relevant):
    relevant=set(relevant)
    return dict(p1=float(bool(ids and ids[0] in relevant)),p3=sum(i in relevant for i in ids[:3])/3,
                hit3=float(bool(set(ids[:3])&relevant)),mrr=next((1/(j+1) for j,i in enumerate(ids[:5]) if i in relevant),0.0))


def worker(method,prep):
    cases=load_cases();sync_cases(cases)
    engine=SearchEngine(load_documents(),method,prep)
    rows=[]
    for case in cases:
        if not case['relevant']:continue
        started=time.perf_counter();hits=engine.search(case['query'],5)
        ids=[r['id'] for r in hits]
        rows.append(dict(case_id=case['id'],query=case['query'],split=case['split'],expected=case['relevant'],predicted=ids,
            scores=[h['score'] for h in hits],latency_ms=(time.perf_counter()-started)*1000,**score_hits(ids,case['relevant'])))
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
    results=[]
    case_hash=hashlib.sha256((DATA/'evaluation.jsonl').read_bytes()).hexdigest()
    for split in ('dev','test'):
        group=[r for r in rows if r['split']==split]
        summary=dict(method=method,preprocessing=prep,split=split,n=len(group),fit_ms=engine.fit_ms,peak_rss_mb=peak,**metrics(group))
        results.append(summary)
        run=str(uuid.uuid4())
        with connect() as conn:
            conn.execute('INSERT INTO evaluation_runs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (run,datetime.now(timezone.utc).isoformat(),method,prep,split,engine.fingerprint+':'+case_hash,
                 summary['p1'],summary['p3'],summary['mrr'],summary['hit3'],summary['latency_ms'],peak,engine.fit_ms))
            for r in group:
                conn.executemany('INSERT INTO predictions VALUES(?,?,?,?,?)',[(run,r['case_id'],j+1,d,r['scores'][j]) for j,d in enumerate(r['predicted'])])
    out=ROOT/'artifacts/evaluation';out.mkdir(parents=True,exist_ok=True)
    (out/f'{method}_{prep}.json').write_text(json.dumps({'metrics':results,'predictions':rows},ensure_ascii=False,indent=2))
    print(method,prep,'test P@1:',round(results[-1]['p1'],3),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--worker');parser.add_argument('--prep',default='lemma');args=parser.parse_args()
    if args.worker:worker(args.worker,args.prep);return
    methods=[('rule','lemma'),('bow','stem'),('bow','lemma'),('tfidf','stem'),('tfidf','lemma'),('bm25','lemma'),('embeddings','lemma'),('hybrid','lemma'),('reranker','lemma'),('verified_hybrid','lemma')]
    for method,prep in methods:
        subprocess.run([sys.executable,'-m','tools.evaluate','--worker',method,'--prep',prep],cwd=ROOT,check=True)
    rows=[]
    for method,prep in methods:rows.extend(json.loads((ROOT/f'artifacts/evaluation/{method}_{prep}.json').read_text())['metrics'])
    with (ROOT/'artifacts/metrics.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

if __name__=='__main__':main()
