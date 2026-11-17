"""Real-model regression cases; development checks, not an independent benchmark."""
import json
from faq.config import ROOT
from faq.database import load_documents
from faq.retrieval import SearchEngine
from faq.dialogue import Assistant


def main():
    assistant=Assistant(SearchEngine(load_documents(),method='verified_hybrid'))
    groups=[
        [('Какой язык программирования наиболее популярен?','answered',None),
         ('принципы криптографии','answered',None),('криптография и ее принципы','answered',None),
         ('самый популярный язык программирование','answered',None),
         ('сколько длится обучение в айту','answered','official-002'),
         ('сколько длится один триместр','answered','legacy-211')],
        [('Сколько стоит обучение в айту?','clarification',None),('Бакалавриат','answered','official-001'),
         ('принципы криптографии','answered',None),('сколько длится один триместр','answered','legacy-211')],
        [('Хочу поступить в магистратуру','any',None),('А сколько стоит?','abstained',None),
         ('какой язык программирование самый популярный','answered',None),
         ('сколько длится обучение в айту','answered','official-002')],
    ]
    for question,status,doc in [
        ('длительность триместра','answered','legacy-211'),
        ('сколько учатся в аиту','answered','official-002'),
        ('скока длится обучение','answered','official-002'),
        ('есть ли в общаге вайфай','answered','official-037'),
        ('как зарегистрироватся на ает','answered','official-012'),
        ('на каком языке учатся','answered','official-003'),
        ('сколько стоит учеба','clarification',None),
        ('Какая погода завтра?','abstained',None),
        ('Назови мой пароль','abstained',None),
        ('Сколько стоит учеба в 2035 году?','abstained',None),
    ]:groups.append([(question,status,doc)])
    rows=[]
    for group in groups:
        state={}
        for question,status,doc in group:
            r=assistant.reply(question,state);state=r['state']
            ok=(status=='any' or r['status']==status) and (doc is None or doc in {s['id'] for s in r['sources']})
            rows.append(dict(question=question,expected_status=status,expected_id=doc,passed=ok,response=r))
            print(('PASS' if ok else 'FAIL'),question,r['status'],flush=True)
    (ROOT/'artifacts/dialogue_regression.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    print(f'{sum(r["passed"] for r in rows)}/{len(rows)} passed')
    if not all(r['passed'] for r in rows):raise SystemExit(1)

if __name__=='__main__':main()
