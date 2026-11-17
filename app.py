"""Student-facing dashboard with conversation, complete corpus and measured research."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from faq.client import request
from faq.config import ROOT
st.set_page_config(page_title='AITU · Campus Answers',page_icon='🎓',layout='wide')
st.markdown('''<style>.block-container{max-width:1120px;padding-top:2rem}h1{letter-spacing:-1.3px}
[data-testid="stMetricValue"]{color:#176b67}footer{visibility:hidden}</style>''',unsafe_allow_html=True)
st.caption('AITU / CAMPUS ANSWERS / УЧЕБНЫЙ ПРОЕКТ')
st.title('Спросите об университете')
st.write('Поступление, экзамены и студенческая жизнь — с источниками и уточнениями.')

@st.cache_data(ttl=60)
def knowledge():return request('/knowledge')

with st.sidebar:
    st.subheader('О помощнике')
    st.write('Локальный поиск по словам и смыслу, затем отдельная проверка релевантности. Без платных API.')
    st.caption('Переписка хранится только в памяти сессии. Неофициальный сервис. Условия поступления сверяйте с университетом.')
    if st.button('Начать новый разговор'):
        st.session_state['messages']=[];st.session_state['context']={};st.rerun()
    try:
        health=request('/health');st.success('Поиск готов · '+str(health['cards'])+' карточки')
    except Exception:st.error('Сервер недоступен. Запустите python3 start.py')
chat,corpus,research,about=st.tabs(['Диалог','База знаний','Исследование','О проекте'])
with chat:
    st.caption('Например: «В общаге есть интернет?», «Как записаться на АЕТ?», «Сколько стоит учеба?»')
    for message in st.session_state.get('messages',[]):
        with st.chat_message(message['role']):
            st.write(message['text'])
            for source in message.get('sources',[]):st.markdown(f"[Источник: {source['category']}]({source['url']})")
    query=st.chat_input('Ваш вопрос об AITU',max_chars=1500)
    if query:
        history=st.session_state.setdefault('messages',[])
        history.append({'role':'user','text':query})
        try:
            with st.spinner('Ищу и проверяю подходящие материалы…'):
                result=request('/chat',{'text':query,'state':st.session_state.get('context',{})})
            st.session_state['context']=result['state']
            history.append({'role':'assistant','text':result['answer'],'sources':result['sources']})
            st.session_state['last_result']=result
            st.rerun()
        except Exception:st.error('Поиск временно недоступен. Проверьте терминал, где запущено приложение.')
    result=st.session_state.get('last_result')
    if result:
        with st.expander('На чём основан ответ'):
            st.caption('Оценка модели — показатель соответствия, а не вероятность правильности.')
            for r in result['candidates']:st.write(r['question']);st.caption(f"{r['source_kind']} · {r['score']:.2f}")
        if result['sources']:
            left,right=st.columns(2)
            for col,label,value in [(left,'Ответ помог',True),(right,'Ответ не помог',False)]:
                if col.button(label):
                    request('/feedback',{'document_id':result['sources'][0]['id'],'helpful':value});st.toast('Спасибо! Сохранена оценка без текста переписки.')
with corpus:
    try:
        records=knowledge();frame=pd.DataFrame(records)
        c1,c2,c3=st.columns(3)
        c1.metric('Карточки',len(frame));c2.metric('Официальные дополнения',int(frame.source_kind.eq('official').sum()));c3.metric('Источники',frame.url.nunique())
        origin=st.selectbox('Происхождение',['Все','Официальные страницы','Исходный датасет'])
        topic=st.selectbox('Раздел',['Все']+sorted(frame.category.unique()))
        phrase=st.text_input('Поиск по вопросам и ответам')
        if origin!='Все':frame=frame[frame.source_kind.eq('official' if origin=='Официальные страницы' else 'dataset')]
        if topic!='Все':frame=frame[frame.category.eq(topic)]
        if phrase:frame=frame[(frame.question+' '+frame.answer).str.contains(phrase,case=False,regex=False)]
        st.caption(f'Показано {len(frame)} карточек. Исходные FAQ не проверены на актуальность; официальные дополнения имеют дату просмотра.')
        st.dataframe(frame[['question','answer','category','source_kind','url','checked_at']],hide_index=True,width='stretch')
        st.download_button('Скачать полный корпус JSON',json.dumps(records,ensure_ascii=False,indent=2),'aitu_corpus.json')
    except Exception:st.info('База появится после запуска локального сервера.')
with research:
    path=ROOT/'artifacts/metrics.csv'
    if path.exists():
        metrics=pd.read_csv(path);split=st.selectbox('Выборка',['test','dev']);show=metrics[metrics.split.eq(split)]
        st.dataframe(show,hide_index=True,width='stretch')
        st.bar_chart(show.assign(label=show.method+' / '+show.preprocessing).set_index('label')[['p1','mrr']],stack=False)
        st.caption('P@3 = число релевантных карточек / 3. MRR@5. Peak RSS измеряется в отдельном процессе вместе с загрузкой. Разметка составлена с помощью ИИ; независимая проверка людьми ещё нужна.')
    else:st.info('Результаты исследования ещё не сформированы.')
    for name in ['frequencies','bigrams','confusion','answerability']:
        path=ROOT/f'artifacts/{name}.png'
        if path.exists():st.image(str(path))
with about:
    st.write('University FAQ Retrieval Chatbot · Programming for Data Analysis and Database · тема 18')
    st.write('Baizhanov Alimzhan · Zhanbolat Karimzhanov · ADA2602M')
    st.write('Python · SQLite · NLTK/spaCy · BoW/TF-IDF/BM25 · E5 embeddings · multilingual cross-encoder')
    st.caption('Вклад участников пока не распределён. Исключение по размеру данных и использование ИИ согласуются с преподавателем.')
