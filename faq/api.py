"""One local inference process shared by Streamlit and Telegram."""
import asyncio
from contextlib import asynccontextmanager
import threading
from fastapi import FastAPI,HTTPException
from pydantic import BaseModel,Field,field_validator
from .database import load_documents,connect
from .retrieval import SearchEngine
from .dialogue import Assistant

assistant=None
lock=threading.Lock()

@asynccontextmanager
async def lifespan(app):
    global assistant
    assistant=await asyncio.to_thread(lambda:Assistant(SearchEngine(load_documents(),method='verified_hybrid')))
    yield

app=FastAPI(title='AITU FAQ · Local Retrieval',lifespan=lifespan)

class Question(BaseModel):
    text:str=Field(min_length=1,max_length=1500)
    state:dict=Field(default_factory=dict)
    @field_validator('text')
    @classmethod
    def nonblank(cls,value):
        if not value.strip():raise ValueError('Введите непустой вопрос')
        return value.strip()

@app.get('/health')
def health():return {'ready':assistant is not None,'cards':len(assistant.engine.records) if assistant else 0,'method':'verified_hybrid','generation':'extractive_local'}

@app.get('/knowledge')
def knowledge():return load_documents()

@app.post('/chat')
def chat(body:Question):
    try:
        with lock:return assistant.reply(body.text,body.state)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

class Feedback(BaseModel):
    document_id:str
    helpful:bool

@app.post('/feedback')
def feedback(body:Feedback):
    import sqlite3
    try:
        with connect() as conn:conn.execute("INSERT INTO feedback(created_at,document_id,helpful) VALUES(datetime('now'),?,?)",(body.document_id,int(body.helpful)))
    except sqlite3.IntegrityError:raise HTTPException(422,'Неизвестный источник') from None
    return {'saved':True}
