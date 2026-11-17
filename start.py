#!/usr/bin/env python3
"""Single entry point for fish/bash: dependencies, SQLite, search, website, Telegram."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
PYTHON=ROOT/'.venv/bin/python'
processes=[]
handles=[]


def announce(text):print(text,flush=True)


def prepare():
    os.chdir(ROOT)
    if not PYTHON.exists():
        announce('1/5 Создаю отдельное окружение Python…')
        subprocess.run([sys.executable,'-m','venv',str(ROOT/'.venv')],check=True)
    fingerprint=hashlib.sha256((ROOT/'requirements.txt').read_bytes()).hexdigest()
    stamp=ROOT/'.venv/.installed'
    if not stamp.exists() or stamp.read_text()!=fingerprint:
        announce('1/5 Устанавливаю библиотеки. Первый запуск может занять несколько минут…')
        subprocess.run([str(PYTHON),'-m','pip','install','-r',str(ROOT/'requirements.txt')],check=True)
        stamp.write_text(fingerprint)
    if Path(sys.prefix).resolve()!=(ROOT/'.venv').resolve():os.execv(str(PYTHON),[str(PYTHON),str(ROOT/'start.py'),*sys.argv[1:]])


def settings(site_only):
    from dotenv import dotenv_values,set_key
    path=ROOT/'.env'
    if not path.exists():
        fd=os.open(path,os.O_CREAT|os.O_WRONLY,0o600);os.close(fd)
    config={k:v for k,v in dotenv_values(path).items() if v is not None}
    for key,value in {'FAQ_API_PORT':'8765','FAQ_WEB_PORT':'8502','FAQ_THREADS':'4','FAQ_OFFLINE':'0'}.items():config.setdefault(key,value)
    if not site_only:
        token=config.get('TELEGRAM_BOT_TOKEN','')
        if not token:
            if not sys.stdin.isatty():raise RuntimeError('Введите токен при запуске в обычном терминале.')
            announce('2/5 Вставьте токен Telegram. Символы не показываются при вводе.')
            token=getpass.getpass('Токен BotFather: ').strip()
        if not re.fullmatch(r'\d+:[\w-]{30,}',token):raise RuntimeError('Токен имеет неверный формат. Скопируйте его целиком из BotFather.')
        try:
            with urllib.request.urlopen('https://api.telegram.org/bot'+token+'/getMe',timeout=20) as r:me=json.load(r)
            if not me.get('ok'):raise ValueError()
        except Exception:raise RuntimeError('Не удалось подключиться к Telegram. Проверьте интернет и токен.') from None
        config['TELEGRAM_BOT_TOKEN']=token
        announce('2/5 Telegram: @'+me['result']['username'])
    for k,v in config.items():set_key(path,k,v)
    path.chmod(0o600)
    os.environ.update(config)
    os.environ.update(FAQ_API_URL='http://127.0.0.1:'+config['FAQ_API_PORT'],OMP_NUM_THREADS=config['FAQ_THREADS'],TOKENIZERS_PARALLELISM='false')
    return config


def check_port(port):
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:s.bind(('127.0.0.1',int(port)))
        except OSError:raise RuntimeError(f'Порт {port} занят. Остановите предыдущий запуск или измените порт в .env.') from None


def launch(name,args):
    log=(ROOT/f'artifacts/logs/{name}.log').open('w');handles.append(log)
    process=subprocess.Popen([str(PYTHON),'-u',*args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    processes.append((name,process))


def check_children():
    for name,p in processes:
        if p.poll() is not None:raise RuntimeError(f'{name} остановился. Подробности в artifacts/logs/{name}.log')


def wait(url,seconds=900):
    deadline=time.monotonic()+seconds;last_message=time.monotonic()
    while time.monotonic()<deadline:
        check_children()
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                if r.status==200:return
        except Exception:pass
        if time.monotonic()-last_message>25:
            announce('Подготовка продолжается: модели загружаются только при первом запуске.');last_message=time.monotonic()
        time.sleep(1)
    raise RuntimeError('Поиск не успел загрузиться. Проверьте интернет и artifacts/logs/api.log.')


def main():
    parser=argparse.ArgumentParser(description='Запустить весь AITU FAQ')
    parser.add_argument('--site-only',action='store_true',help='Диагностический запуск без Telegram')
    args=parser.parse_args();lock=None
    try:
        prepare()
        import fcntl
        folder=ROOT/'artifacts/logs';folder.mkdir(parents=True,exist_ok=True)
        lock=(folder/'run.lock').open('w')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Приложение уже запущено из этой папки.') from None
        config=settings(args.site_only)
        for key in ('FAQ_API_PORT','FAQ_WEB_PORT'):check_port(config[key])
        announce('3/5 Подготавливаю SQLite и полный корпус…')
        from faq.database import sync_corpus
        count=sync_corpus()
        announce(f'3/5 В базе {count} карточки. PostgreSQL и Docker не нужны.')
        announce('4/5 Запускаю локальные модели поиска и проверки ответов…')
        launch('api',['-m','uvicorn','faq.api:app','--host','127.0.0.1','--port',config['FAQ_API_PORT']])
        wait(os.environ['FAQ_API_URL']+'/health')
        launch('site',['-m','streamlit','run','app.py','--server.address','127.0.0.1','--server.port',config['FAQ_WEB_PORT'],'--server.headless','true','--browser.gatherUsageStats','false'])
        site='http://127.0.0.1:'+config['FAQ_WEB_PORT'];wait(site+'/_stcore/health',90)
        if not args.site_only:
            marker=folder/'telegram.ready';marker.unlink(missing_ok=True);os.environ['FAQ_TELEGRAM_READY']=str(marker)
            launch('telegram',['-m','faq.telegram_bot'])
            deadline=time.monotonic()+60
            while not marker.exists():
                check_children()
                if time.monotonic()>deadline:raise RuntimeError('Telegram не стал доступен. Смотрите artifacts/logs/telegram.log')
                time.sleep(1)
            announce('Telegram: https://t.me/'+marker.read_text())
        else:announce('Диагностический режим: Telegram отключён.')
        announce('5/5 Готово. Сайт: '+site+'\nОставьте терминал открытым. Остановка: Ctrl+C.')
        while True:check_children();time.sleep(1)
    except KeyboardInterrupt:announce('\nОстанавливаю приложение. База и настройки сохраняются.')
    except Exception as exc:
        # Never print a token-bearing URL from an HTTP client exception.
        text=str(exc);token=os.getenv('TELEGRAM_BOT_TOKEN','')
        if token:text=text.replace(token,'[TOKEN]')
        announce('Не удалось завершить запуск: '+text);return 1
    finally:
        for _,p in reversed(processes):
            if p.poll() is None:p.terminate()
        for _,p in reversed(processes):
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for h in handles:h.close()
        if lock:lock.close()
    return 0

if __name__=='__main__':sys.exit(main())
