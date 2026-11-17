"""Interactive console interface, independent from Telegram and Streamlit."""
from faq.database import sync_corpus,load_documents
from faq.retrieval import SearchEngine
from faq.dialogue import Assistant
from faq.client import format_answer


def main():
    sync_corpus();assistant=None;state={}
    while True:
        print('\n1 — Задать вопрос\n2 — Найти карточку в базе\n3 — Сбросить разговор\n0 — Выход')
        try:
            choice=input('Выбор: ').strip()
            if choice=='0':break
            elif choice=='1':
                if assistant is None:assistant=Assistant(SearchEngine(load_documents(),method='verified_hybrid'))
                result=assistant.reply(input('Ваш вопрос: '),state);state=result['state'];print(format_answer(result))
            elif choice=='2':
                query=input('Слово или фраза: ').casefold()
                for r in load_documents():
                    if query in (r['question']+' '+r['answer']).casefold():print(r['id'],r['question'])
            elif choice=='3':state={};print('Контекст сброшен')
            else:print('Выберите пункт 0–3')
        except (ValueError,OSError) as exc:print('Ошибка:',exc)
        except (EOFError,KeyboardInterrupt):break

if __name__=='__main__':main()
