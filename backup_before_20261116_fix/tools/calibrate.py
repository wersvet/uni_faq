"""Set answerability threshold from dev only; evaluate frozen policy on test once."""
import json
import hashlib
import numpy as np
from faq.config import ROOT
from faq.database import load_documents
from faq.retrieval import SearchEngine
from faq.dialogue import Assistant
from tools.evaluate import load_cases


def main():
    engine=SearchEngine(load_documents(),method='verified_hybrid');assistant=Assistant(engine)
    cases=load_cases();dev=[c for c in cases if c['split']=='dev']
    observations=[]
    assistant.threshold=-100
    for c in dev:
        r=assistant.reply(c['query'])
        score=max([s['score'] for s in r['sources']],default=-100)
        correct=bool(set(c['relevant'])&{s['id'] for s in r['sources']})
        observations.append((c,r,score,correct))
    choices=[]
    for threshold in np.arange(-5,7.01,.25):
        correct=wrong=miss=0
        for c,r,score,ok in observations:
            accepted=r['status']=='answered' and score>=threshold
            correct+=int(accepted and ok);wrong+=int(accepted and not ok)
            miss+=int(bool(c['relevant']) and not accepted)
        choices.append((correct-2*wrong-.5*miss,float(threshold)))
    _,threshold=max(choices,key=lambda x:(x[0],x[1]))
    policy=dict(threshold=threshold,fingerprint=engine.fingerprint,dialogue_sha256=hashlib.sha256((ROOT/'faq/dialogue.py').read_bytes()).hexdigest(),criterion='dev: correct - 2*wrong - 0.5*miss; raw reranker logit, not probability',dev_n=len(dev))
    (ROOT/'artifacts/answer_policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    assistant.threshold=threshold
    results=[]
    for c in cases:
        r=assistant.reply(c['query'])
        correct=(bool(set(c['relevant'])&{s['id'] for s in r['sources']}) if c['relevant'] else r['status']==c['expected_status'])
        results.append(dict(**c,predicted_status=r['status'],predicted=[s['id'] for s in r['sources']],correct=correct,answer=r['answer']))
    (ROOT/'artifacts/dialogue_evaluation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    for split in ('dev','test'):
        group=[r for r in results if r['split']==split]
        print(split,'correct',sum(r['correct'] for r in group),'/',len(group),'threshold',threshold,flush=True)

if __name__=='__main__':main()
