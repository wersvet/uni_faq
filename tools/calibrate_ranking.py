"""Choose source-authority and hybrid-rank weights using dev relevance labels only."""
import json
from faq.config import ROOT
from faq.database import load_documents
from faq.retrieval import SearchEngine
from tools.evaluate import load_cases,score_hits


def main():
    engine=SearchEngine(load_documents(),'reranker');samples=[]
    for c in load_cases():
        if c['split']=='dev' and c['relevant']:
            hits=engine.search(c['query'],24)
            samples.append({'case':c,'hits':hits})
    candidates=[]
    for weight in [0.,1.,2.,4.,8.]:
        for bonus in [0.,1.,2.,3.,4.]:
            p1=mrr=0
            for sample in samples:
                hits=sorted(sample['hits'],key=lambda r:-(r['score']+weight/r['retrieval_rank']+bonus*(r['source_kind']=='official')))
                m=score_hits([h['id'] for h in hits],sample['case']['relevant']);p1+=m['p1'];mrr+=m['mrr']
            candidates.append((p1,mrr,-bonus,-weight,weight,bonus))
    best=max(candidates)
    policy={'fingerprint':engine.fingerprint,'rank_weight':best[4],'official_bonus':best[5],'dev_p1':best[0]/len(samples),'dev_mrr':best[1]/len(samples),'n':len(samples),'note':'Fitted only on dev. Authority changes ordering, never confidence score. Known queries cover official additions; legacy ranking needs separate human review.'}
    (ROOT/'artifacts/ranking_policy.json').write_text(json.dumps(policy,indent=2)+'\n')
    print(policy,flush=True)

if __name__=='__main__':main()
