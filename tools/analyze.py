"""Frequency/ngram analysis, confusion/error analysis, 12 SQL exports to Pandas."""
from collections import Counter
import json,re
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import ConfusionMatrixDisplay,confusion_matrix
from faq.config import ROOT
from faq.database import connect,load_documents
from faq.text import preprocess


def queries():
    parts=re.split(r'-- name: (\w+)\n',(ROOT/'queries.sql').read_text())
    return {parts[i]:parts[i+1].strip() for i in range(1,len(parts),2)}


def bars(counts,title,path):
    pairs=counts.most_common(16)[::-1]
    fig,ax=plt.subplots(figsize=(10,6));ax.barh([p[0] for p in pairs],[p[1] for p in pairs],color='#176b67')
    ax.set_title(title);ax.set_xlabel('Число употреблений');fig.tight_layout();fig.savefig(path,dpi=150);plt.close(fig)


def main():
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    docs=load_documents();freq=Counter();bigrams=Counter();comparison=[]
    for r in docs:
        words=preprocess(r['question']+' '+r['answer']).split();freq.update(words);bigrams.update(' '.join(p) for p in zip(words,words[1:]))
        comparison.append({'id':r['id'],'text':r['question'],'stem':preprocess(r['question'],'stem'),'lemma':preprocess(r['question'],'lemma')})
    pd.DataFrame(comparison).to_csv(out/'preprocessing_comparison.csv',index=False)
    pd.DataFrame(freq.most_common(),columns=['term','count']).to_csv(out/'frequencies.csv',index=False)
    bars(freq,'Частотные слова: лемматизация, без стоп-слов',out/'frequencies.png')
    bars(bigrams,'Частотные биграммы корпуса',out/'bigrams.png')
    sqlout=out/'sql';sqlout.mkdir(exist_ok=True)
    with connect() as conn:
        for name,sql in queries().items():pd.read_sql_query(sql,conn).to_csv(sqlout/f'{name}.csv',index=False)
    path=out/'evaluation/reranker_lemma.json'
    if path.exists():
        records=json.loads(path.read_text())['predictions'];byid={r['id']:r for r in docs}
        records=[r for r in records if r['split']=='test']
        actual=[byid[r['expected'][0]]['category'] for r in records]
        predicted=[byid[r['predicted'][0]]['category'] for r in records]
        labels=sorted(set(actual+predicted));fig,ax=plt.subplots(figsize=(12,10))
        ConfusionMatrixDisplay.from_predictions(actual,predicted,labels=labels,xticks_rotation=90,cmap='Blues',ax=ax,colorbar=False)
        ax.set_title('Темы источников: reranker, test (не проверка истинности ответа)');fig.tight_layout();fig.savefig(out/'confusion.png',dpi=140);plt.close(fig)
        pd.DataFrame([r for r in records if not r['p1']]).to_csv(out/'retrieval_errors.csv',index=False)
    path=out/'dialogue_evaluation.json'
    if path.exists():
        rows=[r for r in json.loads(path.read_text()) if r['split']=='test']
        labels=['answered','clarification','abstained'];fig,ax=plt.subplots(figsize=(7,5))
        ConfusionMatrixDisplay.from_predictions([r['expected_status'] for r in rows],[r['predicted_status'] for r in rows],labels=labels,ax=ax,cmap='Blues',colorbar=False)
        ax.set_title('Решение: ответ / уточнение / отказ');fig.tight_layout();fig.savefig(out/'answerability.png',dpi=150);plt.close(fig)
        pd.DataFrame([r for r in rows if not r['correct']]).to_csv(out/'dialogue_errors.csv',index=False)
    print('Analysis and SQL exports complete')

if __name__=='__main__':main()
