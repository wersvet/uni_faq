"""SQLite corpus, provenance, keywords and reproducible evaluation runs."""
import json
import sqlite3
from pathlib import Path
from .config import DB,DATA

SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sources(id INTEGER PRIMARY KEY,url TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,checked_at TEXT);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,source_id INTEGER NOT NULL REFERENCES sources(id),question TEXT NOT NULL,answer TEXT NOT NULL,category TEXT NOT NULL,level TEXT NOT NULL,audience TEXT NOT NULL,intent TEXT NOT NULL,valid_year TEXT,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS aliases(id INTEGER PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id),text TEXT NOT NULL,UNIQUE(document_id,text));
CREATE TABLE IF NOT EXISTS keywords(id INTEGER PRIMARY KEY,word TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS document_keywords(document_id TEXT REFERENCES documents(id),keyword_id INTEGER REFERENCES keywords(id),PRIMARY KEY(document_id,keyword_id));
CREATE TABLE IF NOT EXISTS test_cases(id TEXT PRIMARY KEY,query TEXT NOT NULL,split TEXT NOT NULL,expected_status TEXT NOT NULL,topic TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS relevance(case_id TEXT REFERENCES test_cases(id),document_id TEXT REFERENCES documents(id),PRIMARY KEY(case_id,document_id));
CREATE TABLE IF NOT EXISTS evaluation_runs(id TEXT PRIMARY KEY,created_at TEXT NOT NULL,method TEXT NOT NULL,preprocessing TEXT NOT NULL,split TEXT NOT NULL,fingerprint TEXT NOT NULL,p1 REAL,p3 REAL,mrr REAL,hit3 REAL,latency_ms REAL,peak_rss_mb REAL,fit_ms REAL);
CREATE TABLE IF NOT EXISTS predictions(run_id TEXT REFERENCES evaluation_runs(id),case_id TEXT REFERENCES test_cases(id),rank INTEGER,document_id TEXT REFERENCES documents(id),score REAL,PRIMARY KEY(run_id,case_id,rank));
CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL,document_id TEXT REFERENCES documents(id),helpful INTEGER NOT NULL CHECK(helpful IN (0,1)));
CREATE INDEX IF NOT EXISTS docs_source ON documents(source_id);
CREATE INDEX IF NOT EXISTS predictions_doc ON predictions(document_id);
'''


def connect(path=DB):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path,timeout=30)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def initialize(path=DB):
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.execute('PRAGMA journal_mode=WAL')
    return path


def sync_corpus(path=DB):
    initialize(path)
    docs=json.loads((DATA/'corpus.json').read_text())
    from .text import preprocess
    with connect(path) as conn:
        for r in docs:
            conn.execute('INSERT INTO sources(url,kind,checked_at) VALUES(?,?,?) ON CONFLICT(url) DO UPDATE SET kind=excluded.kind,checked_at=excluded.checked_at',(r['url'],r['source_kind'],r['checked_at']))
            sid=conn.execute('SELECT id FROM sources WHERE url=?',(r['url'],)).fetchone()[0]
            conn.execute('''INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
            source_id=excluded.source_id,question=excluded.question,answer=excluded.answer,category=excluded.category,level=excluded.level,audience=excluded.audience,intent=excluded.intent,valid_year=excluded.valid_year,status=excluded.status''',
                (r['id'],sid,*[r[k] for k in ['question','answer','category','level','audience','intent','valid_year','status']]))
            conn.execute('DELETE FROM aliases WHERE document_id=?',(r['id'],))
            conn.executemany('INSERT INTO aliases(document_id,text) VALUES(?,?)',[(r['id'],a) for a in r['aliases']])
            conn.execute('DELETE FROM document_keywords WHERE document_id=?',(r['id'],))
            for word in set(preprocess(r['question']).split()):
                conn.execute('INSERT OR IGNORE INTO keywords(word) VALUES(?)',(word,))
                conn.execute('INSERT OR IGNORE INTO document_keywords SELECT ?,id FROM keywords WHERE word=?',(r['id'],word))
    return len(docs)


def load_documents(path=DB):
    with connect(path) as conn:
        rows=conn.execute('SELECT d.*,s.url,s.kind AS source_kind,s.checked_at FROM documents d JOIN sources s ON d.source_id=s.id ORDER BY d.id').fetchall()
        aliases={}
        for row in conn.execute('SELECT document_id,text FROM aliases'):aliases.setdefault(row[0],[]).append(row[1])
        return [dict(r,aliases=aliases.get(r['id'],[])) for r in rows]


def sync_cases(cases,path=DB):
    with connect(path) as conn:
        for c in cases:
            conn.execute('INSERT INTO test_cases VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET query=excluded.query,split=excluded.split,expected_status=excluded.expected_status,topic=excluded.topic',tuple(c[k] for k in ['id','query','split','expected_status','topic']))
            conn.execute('DELETE FROM relevance WHERE case_id=?',(c['id'],))
            conn.executemany('INSERT INTO relevance VALUES(?,?)',[(c['id'],d) for d in c['relevant']])
