"""Full-content retrieval, lexical/dense fusion, multilingual cross-encoder reranking."""
import hashlib
import json
import os
import time
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer,TfidfVectorizer
from sklearn.preprocessing import normalize as l2_normalize
from .config import ROOT,EMBED_MODEL,EMBED_REVISION,RERANK_MODEL,RERANK_REVISION
from .text import normalize,preprocess

METHODS=['rule','bow','tfidf','bm25','embeddings','hybrid','reranker','verified_hybrid']


def document_text(r):
    return f"Раздел: {r['category']}. Вопрос: {r['question']}\nОтвет: {r['answer']}\nДругие формулировки: "+' ; '.join(r.get('aliases',[]))


def fingerprint(records):
    h=hashlib.sha256(json.dumps(records,sort_keys=True,ensure_ascii=False).encode())
    for name in ('retrieval.py','text.py'):
        h.update((ROOT/'faq'/name).read_bytes())
    h.update((EMBED_MODEL+EMBED_REVISION+RERANK_MODEL+RERANK_REVISION).encode())
    return h.hexdigest()


class SearchEngine:
    def __init__(self,records,method='reranker',preprocessing='lemma'):
        if method not in METHODS:raise ValueError('Unknown retrieval method')
        self.records=records;self.method=method;self.preprocessing=preprocessing
        self.texts=[document_text(r) for r in records]
        self.encoder=None;self.reranker=None
        self.fingerprint=fingerprint(records)
        started=time.perf_counter()
        self.processed=[preprocess(t,preprocessing) for t in self.texts]
        self.vectorizer=CountVectorizer(tokenizer=str.split,token_pattern=None,lowercase=False)
        self.counts=self.vectorizer.fit_transform(self.processed).astype(np.float32)
        self.bow=l2_normalize(self.counts)
        self.tfidf_vectorizer=TfidfVectorizer(tokenizer=str.split,token_pattern=None,lowercase=False)
        self.tfidf=self.tfidf_vectorizer.fit_transform(self.processed).astype(np.float32)
        self.lengths=np.asarray(self.counts.sum(axis=1)).ravel()
        self.average_length=max(1,float(self.lengths.mean()))
        df=np.asarray((self.counts>0).sum(axis=0)).ravel()
        self.idf=np.log(1+(len(records)-df+.5)/(df+.5))
        if method in ('embeddings','hybrid','reranker','verified_hybrid'):self._load_dense()
        if method in ('reranker','verified_hybrid'):self._load_reranker()
        self.fit_ms=(time.perf_counter()-started)*1000

    def _load_dense(self):
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(int(os.getenv('FAQ_THREADS','4')))
        offline=os.getenv('FAQ_OFFLINE')=='1'
        self.encoder=SentenceTransformer(EMBED_MODEL,revision=EMBED_REVISION,device='cpu',local_files_only=offline,trust_remote_code=False)
        path=ROOT/'artifacts/cache'/f'{self.fingerprint}.npy'
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            matrix=np.load(path,allow_pickle=False)
            if matrix.shape==(len(self.records),768):self.dense=matrix;return
        self.dense=self.encoder.encode(['passage: '+t for t in self.texts],batch_size=16,normalize_embeddings=True,show_progress_bar=False).astype(np.float32)
        temp=path.with_suffix('.tmp.npy');np.save(temp,self.dense);temp.replace(path)

    def _load_reranker(self):
        from sentence_transformers import CrossEncoder
        self.reranker=CrossEncoder(RERANK_MODEL,revision=RERANK_REVISION,device='cpu',max_length=384,local_files_only=os.getenv('FAQ_OFFLINE')=='1',trust_remote_code=False)

    def bm25_scores(self,processed):
        q=self.vectorizer.transform([processed])
        scores=np.zeros(len(self.records),dtype=np.float32)
        for j in q.indices:
            tf=self.counts[:,j].toarray().ravel()
            scores+=self.idf[j]*(tf*2.5)/(tf+1.5*(.25+.75*self.lengths/self.average_length))
        return scores

    def search(self,query,k=5,eligible=None):
        if not isinstance(query,str) or not query.strip() or len(query)>1500:raise ValueError('Введите вопрос от 1 до 1500 символов.')
        query=normalize(query)
        processed=preprocess(query,self.preprocessing)
        valid=np.array([i for i,r in enumerate(self.records) if eligible is None or eligible(r)],dtype=int)
        if not len(valid):return []
        if self.method=='rule':
            q=set(processed.split());scores=np.array([len(q&set(t.split()))/max(1,len(q|set(t.split()))) for t in self.processed])
        elif self.method=='bow':scores=(self.bow@l2_normalize(self.vectorizer.transform([processed])).T).toarray().ravel()
        elif self.method=='tfidf':scores=(self.tfidf@self.tfidf_vectorizer.transform([processed]).T).toarray().ravel()
        elif self.method=='bm25':scores=self.bm25_scores(processed)
        else:
            vector=self.encoder.encode(['query: '+query],normalize_embeddings=True,show_progress_bar=False)[0]
            dense=self.dense@vector
            if self.method=='embeddings':scores=dense
            else:
                lexical=self.bm25_scores(processed)
                scores=np.zeros(len(self.records),dtype=np.float32)
                for component in (dense,lexical):
                    order=valid[np.argsort(-component[valid],kind='stable')]
                    scores[order]+=1/(60+np.arange(1,len(order)+1))
        order=valid[np.argsort(-scores[valid],kind='stable')]
        ranks={int(i):j+1 for j,i in enumerate(order)}
        raw_scores=None
        if self.method in ('reranker','verified_hybrid'):
            import torch
            candidates=order[:min(24,len(order))]
            relevance=self.reranker.predict([(query,self.texts[i]) for i in candidates],batch_size=8,show_progress_bar=False,activation_fn=torch.nn.Identity())
            order=candidates[np.argsort(-np.asarray(relevance),kind='stable')]
            scores=np.full(len(self.records),-100.,dtype=float)
            scores[candidates]=np.asarray(relevance).ravel()
            raw_scores=scores.copy()
            if self.method=='verified_hybrid':
                policy_path=ROOT/'artifacts/ranking_policy.json'
                policy=json.loads(policy_path.read_text()) if policy_path.exists() else {}
                if policy.get('fingerprint')==self.fingerprint:
                    for i in candidates:
                        scores[i]+=policy['rank_weight']/ranks[int(i)]+policy['official_bonus']*(self.records[i]['source_kind']=='official')
                order=candidates[np.argsort(-scores[candidates],kind='stable')]
        return [dict(self.records[int(i)],score=float(raw_scores[i] if raw_scores is not None else scores[i]),ranking_score=float(scores[i]),retrieval_rank=ranks[int(i)]) for i in order[:k]]
