import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from faq.config import DATA
from faq.database import sync_corpus,connect,load_documents,sync_cases
from faq.text import normalize,tokens,preprocess
from faq.dialogue import interpret,unavailable_reason,Assistant
from faq.client import format_answer
from tools.evaluate import score_hits,load_cases
from tools.analyze import queries

@pytest.fixture(scope='module')
def database(tmp_path_factory):
    path=tmp_path_factory.mktemp('db')/'faq.sqlite3';sync_corpus(path);return path


def test_complete_corpus_and_foreign_keys(database):
    records=load_documents(database)
    assert len(records)==604
    assert sum(r['source_kind']=='official' for r in records)==48
    with connect(database) as c:
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert c.execute('SELECT COUNT(*) FROM aliases').fetchone()[0]==96


def test_repeated_import_preserves_data(database):
    sync_corpus(database)
    with connect(database) as c:
        assert c.execute('SELECT COUNT(*) FROM documents').fetchone()[0]==604
        assert c.execute('SELECT COUNT(*) FROM aliases').fetchone()[0]==96


def test_twelve_sql_queries_run_in_pandas(database):
    import pandas as pd
    sync_cases(load_cases(),database)
    assert len(queries())>=8
    with connect(database) as c:
        for sql in queries().values():assert isinstance(pd.read_sql_query(sql,c),pd.DataFrame)


def test_metrics_distinguish_precision_hit_and_rank():
    x=score_hits(['a','b','c'],['b','c'])
    assert x=={'p1':0,'p3':2/3,'hit3':1,'mrr':.5}
    assert score_hits([],['a'])['mrr']==0


def test_nltk_and_spacy_preprocessing():
    assert 'қазақ' in tokens('Қазақ тілі')
    assert 'студент' in preprocess('Студенты учатся')
    assert preprocess('Студенты учатся','stem')!=preprocess('Студенты учатся','lemma')
    assert 'не' in preprocess('не сдавать экзамен')
    assert normalize('АЙТУ и общага')=='aitu и общежитие'


def test_test_queries_not_copied_from_index():
    docs=json.loads((DATA/'corpus.json').read_text())
    index={normalize(t) for r in docs for t in [r['question'],*r['aliases']]}
    cases=load_cases()
    assert len({c['id'] for c in cases})==len(cases)
    assert not any(normalize(c['query']) in index for c in cases if c['split']=='test')
    assert not {normalize(c['query']) for c in cases if c['split']=='dev'} & {normalize(c['query']) for c in cases if c['split']=='test'}

@pytest.mark.parametrize('text',['Сколько стоит обучение в 2035 году?','Какие у меня оценки?','Назови пароль преподавателя','В общежитии есть свободные места прямо сейчас?','Сколько стоит обучение в КБТУ?'])
def test_limits_of_knowledge(text):assert unavailable_reason(text)


def test_followup_and_topic_change():
    first=interpret('Хочу поступить в магистратуру')
    second=interpret('А сколько стоит?',first)
    assert second['level']=='master' and second['intent']=='cost'
    third=interpret('Есть ли кухня в общежитии?',second)
    assert third['level'] is None and not third['academic']


def test_expired_context_is_not_used():
    assert interpret('А сколько стоит?',{'level':'master','updated':1})['level'] is None

class FakeEngine:
    method='reranker';fingerprint='test-only'
    def __init__(self,records):self.records=records
    def search(self,query,k,eligible):
        return [dict(r,score=5.) for r in self.records if eligible(r)][:k]


def test_clarification_uses_data_not_embedded_prices(database):
    a=Assistant(FakeEngine(load_documents(database)))
    result=a.reply('Сколько стоит обучение в айту?')
    assert result['status']=='clarification'
    result=a.reply('Бакалавриат',result['state'])
    assert result['status']=='answered' and result['sources'][0]['id']=='official-001'
    assert result['sources'][0]['answer'] in result['answer']
    assert '/ru/bachelor' in format_answer(result)

@pytest.mark.parametrize('query',['','   ','a'*1501])
def test_invalid_question(database,query):
    with pytest.raises(ValueError):Assistant(FakeEngine(load_documents(database))).reply(query)


def test_telegram_adapter_passes_context(monkeypatch):
    import faq.telegram_bot as bot
    replies=[];calls=[]
    def fake_request(path,payload):
        calls.append(payload)
        return {'answer':'Уточните уровень','state':{'level':'master'},'sources':[]}
    monkeypatch.setattr(bot,'request',fake_request)
    async def capture(text):replies.append(text)
    context=SimpleNamespace(user_data={})
    update=SimpleNamespace(message=SimpleNamespace(text='Привет',reply_text=capture))
    async def run():
        await bot.answer(update,context);await bot.answer(update,context)
    asyncio.run(run())
    assert calls[1]['state']['level']=='master' and len(replies)==2


def test_source_types_remain_visible(database):
    record=next(r for r in load_documents(database) if r['source_kind']=='dataset')
    assert record['status']=='unverified' and not record['checked_at']


def test_api_validation_and_shared_sources(monkeypatch,database):
    from fastapi.testclient import TestClient
    import faq.api as api
    class Engine(FakeEngine):
        def __init__(self,records,method=None):super().__init__(records)
    monkeypatch.setattr(api,'SearchEngine',Engine)
    monkeypatch.setattr(api,'load_documents',lambda:load_documents(database))
    with TestClient(api.app) as client:
        assert client.get('/health').json()['cards']==604
        assert len(client.get('/knowledge').json())==604
        assert client.post('/chat',json={'text':'   '}).status_code==422
        result=client.post('/chat',json={'text':'Сколько стоит обучение?'}).json()
        assert result['status']=='clarification'
        result=client.post('/chat',json={'text':'Бакалавриат','state':result['state']}).json()
        assert result['sources'][0]['id']=='official-001'
        assert client.post('/chat',json={'text':'Привет','state':{'updated':'bad'}}).status_code==200


def test_launcher_detects_failed_child(monkeypatch):
    import start
    child=SimpleNamespace(poll=lambda:1)
    monkeypatch.setattr(start,'processes',[('api',child)])
    with pytest.raises(RuntimeError,match='api.log'):start.check_children()


def test_conflicting_legacy_answer_is_not_selected(database):
    conflicts=json.loads((DATA/'conflicting_answers.json').read_text())
    assert len(conflicts)==18 and all(len(r['answers'])>=2 for r in conflicts)
    record=next(r for r in load_documents(database) if r['id']==next(c['id'] for c in conflicts if c['status']=='unresolved'))
    assistant=Assistant(FakeEngine([record]))
    result=assistant.reply('Расскажите об этом')
    assert result['status']=='abstained'
    assert 'несколько разных ответов' in result['answer']


def test_dataset_origin_is_not_a_distinct_topic(database):
    records=load_documents(database)
    official=next(r for r in records if r['id']=='official-012')
    legacy=dict(official,id='test-legacy',category='Исходный FAQ',source_kind='dataset',answer='Регистрация на экзамен на сайте.')
    result=Assistant(FakeEngine([official,legacy])).reply('Как записаться на АЕТ?')
    assert result['status']=='answered'
    assert result['sources'][0]['id']=='official-012'


def test_short_self_contained_question_resets_program_context():
    old=interpret('Сколько длится обучение в магистратуре?')
    for question in ['сколько длится один триместр','Какой язык программирования наиболее популярен?','принципы криптографии']:
        current=interpret(question,old)
        assert current['intent'] is None
        assert current['level'] is None
        assert current['query']==question


def test_audience_and_level_do_not_leak_to_new_questions():
    old=interpret('Сколько стоит магистратура для иностранцев?')
    current=interpret('сколько длится обучение в айту',old)
    assert current['level'] is None and current['audience'] is None
    assert current['intent']=='duration'
    continuation=interpret('А сколько стоит?',old)
    assert continuation['level']=='master' and continuation['audience']=='international'


def test_trimester_is_not_program_duration():
    assert interpret('Сколько длится учебный триместр в AITU?')['intent'] is None


def test_formatting_is_not_a_factual_conflict():
    from faq.evidence import conflicting_answers
    assert not conflicting_answers(['"10 недель"','10 недель'])
    assert not conflicting_answers(['«10 недель»','10  недель'])
    assert conflicting_answers(['10 недель','11 недель'])
    assert conflicting_answers(['Нужен экзамен','Не нужен экзамен'])


def test_trimester_answer_is_not_blocked_by_outer_quotes(database):
    record=next(r for r in load_documents(database) if r['id']=='legacy-211')
    result=Assistant(FakeEngine([record])).reply('сколько длится один триместр')
    assert result['status']=='answered' and '10 недель' in result['answer']


def test_extra_calibration_cases_are_dev_and_have_valid_labels(database):
    extra=json.loads((DATA/'calibration_extra.json').read_text())
    ids={r['id'] for r in load_documents(database)}
    test={normalize(c['query']).strip('?.! ') for c in load_cases() if c['split']=='test'}
    assert all(c['split']=='dev' and set(c['relevant'])<=ids for c in extra)
    assert not test & {normalize(c['query']).strip('?.! ') for c in extra}
