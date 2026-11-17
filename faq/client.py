import json
import os
import urllib.request


def request(path,payload=None):
    base=os.getenv('FAQ_API_URL','http://127.0.0.1:8765')
    req=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)


def format_answer(result):
    text=result['answer'];seen=set()
    for source in result['sources']:
        if source['url'] in seen:continue
        seen.add(source['url'])
        text+='\n\nИсточник: '+source['url']
        if source.get('checked_at'):text+='\nПросмотрен: '+source['checked_at']
    return text
