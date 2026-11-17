import hashlib,json,platform
from importlib.metadata import version
from faq.config import ROOT,EMBED_MODEL,EMBED_REVISION,RERANK_MODEL,RERANK_REVISION


def main():
    paths=['data/raw.parquet','data/original_faq.parquet','data/corpus.json','data/evaluation.jsonl','data/conflicting_answers.json','requirements.txt']
    manifest={'python':platform.python_version(),'platform':platform.platform(),'files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'models':{EMBED_MODEL:EMBED_REVISION,RERANK_MODEL:RERANK_REVISION},'packages':{p:version(p) for p in ['spacy','nltk','torch','sentence-transformers','scikit-learn','pandas','streamlit','python-telegram-bot']}}
    (ROOT/'artifacts/manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
