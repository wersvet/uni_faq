"""Conversation state and evidence selection; facts always come from the SQLite corpus."""
import json
import hashlib
import re
import time
from .config import ROOT
from .text import normalize


def interpret(query,state=None):
    state=dict(state or {})
    allowed={'query':str,'level':str,'audience':str,'intent':str,'academic':bool,'updated':(int,float)}
    state={k:v for k,v in state.items() if k in allowed and isinstance(v,allowed[k])}
    if len(state.get('query',''))>1500:state={}
    age=time.time()-state.get('updated',0)
    if age>1800 or age<0:state={}
    q=normalize(query)
    level='master' if re.search(r'магистр|после бакалавр',q) else 'bachelor' if re.search(r'бакалавр|после школы|после 11',q) else None
    audience='international' if re.search(r'иностран|не гражданин|другой стран|не из казахстан|из другой стран',q) else None
    study=bool(re.search(r'обуч|учеб|учит|универ|aitu|бакалавр|магистр|после школы|после 11',q))
    other=bool(re.search(r'общежит|общаг|экзамен|а[еэ]т|aet|курс\b|курсах|воен|обмен|мобильност|стир|кухн|регистратор|кредит',q))
    short_followup=len(q.split())<=7 and bool(state)
    academic=(study or (short_followup and state.get('academic'))) and not other
    intent=None
    if academic:
        if re.search(r'стоим|стоит|цен|сколько.*(?:плат|денег)|во сколько.*обойд',q):intent='cost'
        elif re.search(r'длит|продолжительност|заканчива|срок|долго|сколько.*(?:лет|учит)',q):intent='duration'
        elif re.search(r'язык|по.русски|английск|казахск',q):intent='language'
    pure_slot=bool(re.fullmatch(r'(?:а |на |для |про )*(?:бакалавр\w*|магистр\w*|иностран\w*)(?:\s+(?:для\s+)?иностран\w*)?[?.!]*',q))
    if pure_slot and state:
        intent=state.get('intent');academic=state.get('academic',False)
        effective=state.get('query','')+' '+query
    else:effective=query
    if not level and short_followup and not other:level=state.get('level')
    if not audience and short_followup and not other:audience=state.get('audience')
    # Never carry a guessed audience into a new, self-contained question.
    if level:effective+=' '+('магистратура' if level=='master' else 'бакалавриат')
    if audience:effective+=' для иностранных абитуриентов'
    result=dict(query=effective,level=level,audience=audience,intent=intent,academic=academic,updated=time.time())
    return result


def unavailable_reason(query):
    q=normalize(query)
    if re.search(r'игнорируй|игнорир.*источник|придумай.*услов|выдумай',q):return 'Я отвечаю по материалам университета и не придумываю условия поступления.'
    if re.search(r'назарбаев|кбту|kbtu|гарвард|мгу|казну|enu\b',q):return 'Моя база относится к Astana IT University. Для другого университета нужен его официальный источник.'
    if re.search(r'парол|мои оценки|у меня.*оцен|мой.*средний балл|у меня.*(?:экзамен|балл)|моя пара|доход.*декан|зарабатывает.*преподавател|зарплат',q):return 'У меня нет доступа к личным кабинетам, персональным данным и индивидуальному расписанию.'
    if re.search(r'(?:сейчас|прямо сейчас|завтра|сегодня).*свобод|свобод.*(?:сейчас|прямо сейчас)',q):return 'В базе нет данных о свободных местах в реальном времени. Их нужно уточнить у администрации общежития.'
    years=set(re.findall(r'\b20\d{2}\b',q))
    if years and not years<={'2026','2027'}:return 'Для указанного года в базе нет подтверждённых условий. Уточните учебный год или обратитесь в приёмную комиссию.'
    if re.search(r'гарантир|точно дадут|точно получу',q) and 'грант' in q:return 'Я не могу гарантировать грант: результат зависит от конкурса и действующих правил.'
    return None


class Assistant:
    def __init__(self,engine):
        self.engine=engine
        conflicts_path=ROOT/'data/conflicting_answers.json'
        self.conflicts={r['id'] for r in json.loads(conflicts_path.read_text())} if conflicts_path.exists() else set()
        self.threshold=0.0  # raw cross-encoder logit, NOT probability
        path=ROOT/'artifacts/answer_policy.json'
        if path.exists():
            policy=json.loads(path.read_text())
            if policy.get('fingerprint')==engine.fingerprint and policy.get('dialogue_sha256')==hashlib.sha256((ROOT/'faq/dialogue.py').read_bytes()).hexdigest():self.threshold=float(policy['threshold'])

    def reply(self,query,state=None):
        if not isinstance(query,str) or not query.strip() or len(query)>1500:raise ValueError('Введите вопрос от 1 до 1500 символов.')
        slots=interpret(query,state)
        def response(status,text,sources=None,candidates=None):
            return dict(status=status,answer=text,sources=sources or [],candidates=candidates or [],state=slots,method=self.engine.method)
        reason=unavailable_reason(query)
        if reason:return response('abstained',reason)
        if slots['intent']=='cost' and not slots['level']:
            return response('clarification','Уточните, пожалуйста: бакалавриат или магистратура? Если вы иностранный абитуриент, укажите это — тарифы отличаются.')
        def eligible(r):
            if slots['level'] and r['level'] not in ('any',slots['level']):return False
            if r['audience']=='international' and slots['audience']!='international':return False
            if slots['intent']:
                # Structured facts: no hard-coded answer IDs or factual strings.
                return r['source_kind']=='official' and slots['intent'] in r['intent'].split('|') and (r['audience']=='international')==(slots['audience']=='international')
            return True
        hits=self.engine.search(slots['query'],k=8,eligible=eligible)
        if not hits:
            return response('abstained','Для этих условий в базе нет подтверждённого ответа. Можно уточнить программу или обратиться в приёмную комиссию: admission@astanait.edu.kz.')
        # Source authority only breaks close relevance ties; it cannot make an irrelevant document valid.
        top=hits[0]
        if top['score']<self.threshold:
            return response('abstained','Не нашёл достаточно подходящего источника. Уточните тему, программу или вид экзамена. Для условий поступления: admission@astanait.edu.kz.',candidates=hits[:3])
        if top['id'] in self.conflicts:
            return response('abstained','В исходном датасете есть несколько разных ответов на эту тему. Я не буду выбирать произвольную версию. Уточните условия по официальному источнику или в приёмной комиссии.',candidates=hits[:3])
        selected=[top]
        if slots['intent'] in ('duration','language') and not slots['level']:
            selected=[]
            for level in ('bachelor','master'):
                found=next((r for r in hits if r['level']==level and r['score']>=self.threshold),None)
                if found:selected.append(found)
        elif len(hits)>1 and abs(top['score']-hits[1]['score'])<.25 and hits[1]['id']!=top['id'] and top['answer'].strip()!=hits[1]['answer'].strip() and not slots['intent']:
            # Offer grounded options when several distinct topics are equally likely.
            if (top['category']!=hits[1]['category']
                    and top.get('source_kind')=='official'
                    and hits[1].get('source_kind')=='official'):
                return response('clarification','Нашёл несколько близких тем. Что именно вас интересует?\n\n'+'\n'.join('• '+r['question'] for r in [top,hits[1]]),candidates=[top,hits[1]])
        paragraphs=[]
        labels={'bachelor':'Бакалавриат','master':'Магистратура','any':''}
        for r in selected:
            prefix=(labels[r['level']]+': ') if len(selected)>1 else ''
            paragraphs.append(prefix+r['answer'].strip().strip('"'))
        if any(r['source_kind']=='dataset' for r in selected):paragraphs.append('Примечание: этот ответ есть в исходном учебном датасете; актуальность условий не подтверждена.')
        return response('answered','\n\n'.join(paragraphs),selected,hits[:3])
