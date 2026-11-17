"""Rebuild written PDF/Markdown report from measured artifacts; never invent metrics."""
import json
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from faq.config import ROOT


def main():
    metrics=pd.read_csv(ROOT/'artifacts/metrics.csv');test=metrics[metrics.split.eq('test')]
    dialogue=json.loads((ROOT/'artifacts/dialogue_evaluation.json').read_text());held=[r for r in dialogue if r['split']=='test']
    answered=[r for r in held if r['predicted_status']=='answered'];correct=sum(r['correct'] for r in held)
    mistakes=[r for r in held if not r['correct']]
    policy=json.loads((ROOT/'artifacts/ranking_policy.json').read_text())
    best=test.sort_values(['p1','mrr'],ascending=False).iloc[0]
    sections=[
    ('University FAQ Retrieval Chatbot',[
      'Итоговый проект по дисциплине Programming for Data Analysis and Database. Образовательная программа Big Data Analysis, магистратура. Тема 18. Дата подготовки: 15.11.2026.',
      'Команда: Baizhanov Alimzhan, Zhanbolat Karimzhanov, ADA2602M. Вклад участников на момент подготовки не распределён: это прямо подтверждено пользователем. До сдачи каждый участник должен указать фактически выполненную работу.',
      'Цель: находить подходящий FAQ или официальный фрагмент по естественному вопросу студента, приводить источник и корректно обрабатывать неоднозначность либо отсутствие данных.',
      'Результат: новое самостоятельное Python-приложение. Streamlit и Telegram используют один локальный API, один поисковый процесс и SQLite. Основной режим не требует платных API и не использует генеративную LLM: ответ извлекается из найденных записей.',
      'Проект не является официальным сервисом AITU. Автоматические проверки подтверждают технические сценарии, но не заменяют человеческую проверку фактов, разметки и понимания кода участниками.'
    ]),
    ('Данные и происхождение',[
      'Исходный AITUAdmissionsGuideDataset содержит 608 строк. Число 704 является максимальным старым индексом, а не количеством записей. Исходник сохранён в raw.parquet; снимок содержит по одной записи на 556 уникальных вопросов и сохраняет стабильные идентификаторы. После удаления одной строки-заголовка и 29 точных дублей остаётся 578 пар вопрос–ответ; 18 вопросов имеют разные ответы. Все варианты сохранены в raw.parquet и conflicting_answers.json, их истинность автоматически не выбирается.',
      'Официальный слой включает 48 кратких карточек по 9 страницам AITU: бакалавриат, магистратура, AET, обмен, общежитие, военная кафедра, офис регистратора, международное поступление. Указаны URL, дата просмотра и статус проверки. Полный корпус содержит 604 записи.',
      'Для 48 карточек добавлены 96 поисковых вариантов. Они хранятся как aliases и не выдаются за новые факты. Поисковый текст включает вопрос, ответ, раздел и варианты формулировок. В контрольный набор не включены дословные поисковые варианты.',
      'Старые ответы сохраняются и участвуют в поиске, но помечаются как unverified. При близкой релевантности официальный источник получает приоритет. Поддерживаются признаки уровня обучения, аудитории, намерения вопроса и учебного года.',
      'Объём существенно меньше 500 тысяч строк и 200 МБ. Тема 18 указана в задании среди возможных исключений; согласование преподавателя ещё требуется. Использование Parquet и пакетного кодирования реальное, обработка искусственно раздутого датасета не имитируется.'
    ]),
    ('Архитектура и работа диалога',[
      'start.py создаёт отдельное окружение, устанавливает закреплённые зависимости, сохраняет токен в локальном .env, синхронизирует SQLite и запускает API, сайт и Telegram. Все процессы завершаются по Ctrl+C; база и настройки сохраняются. PostgreSQL и Docker не нужны.',
      'API загружает модели один раз. Два интерфейса передают вопрос и ограниченное состояние диалога; состояние хранится в памяти и истекает через 30 минут. Текст пользовательской переписки в SQLite не записывается.',
      'Сначала проверяются пределы знаний: персональные сведения, другой вуз, неподтверждённый год и информация в реальном времени. Затем определяются уровень обучения и контекст. Если цена зависит от неуказанного уровня, бот уточняет его и понимает короткое продолжение.',
      'Поиск собирает кандидатов по BM25 и смысловым векторам, объединяет позиции RRF и оценивает пары вопрос-документ cross-encoder. Настроенные на dev поправки учитывают исходный ранг и официальный источник. Они меняют порядок, но не повышают исходную оценку уверенности.',
      'Ни цена, ни сроки обучения не зашиты в программные ответы: они берутся из SQLite. Ограниченные правила распознают контекст и тип вопроса. Обработка сложных составных запросов и долгих разговоров остаётся направлением развития.'
    ]),
    ('Предобработка и сравниваемые методы',[
      'Unicode-токенизация сохраняет кириллицу, в том числе казахские буквы. Применяется локальный список стоп-слов; отрицания сохраняются. Нормализуются варианты АИТУ/айту и общежития. Частотные слова и биграммы визуализируются barplot.',
      'Stemming выполняется NLTK Russian Snowball. Lemmatization выполняется компонентом spaCy Russian в режиме pymorphy3. Это spaCy pipeline, без скачивания модели распознавания сущностей. Примеры и результаты сравнения stem/lemma сохранены в CSV.',
      'Baseline rule сравнивает множества терминов. BoW использует нормированные счётчики; TF-IDF учитывает редкость терминов. BM25 дополнительно нормализует длину документа. BoW и TF-IDF проверены со stemming и лемматизацией.',
      'Embeddings: multilingual-e5-base, закреплённая ревизия, нормированные векторы, префиксы query: и passage:. Модель использует исходный текст, не стеммы. Hybrid объединяет BM25 и E5 через RRF с константой 60.',
      'Reranker: multilingual mmarco-mMiniLMv2-L12-H384-v1. Он проверяет до 24 кандидатов и возвращает raw logits. Verified hybrid дополнительно использует приоритет источника и исходный ранг. Модели не дообучались на тестовых вопросах.',
      f'На dev выбраны rank_weight={policy["rank_weight"]} и official_bonus={policy["official_bonus"]}. Один reranker не объявляется лучшим заранее: сравнение включает все варианты.'
    ]),
    ('Протокол и измеренные результаты',[
      'Набор содержит 122 AI-assisted вопроса: dev 61 и test 61. В каждом 48 вопросов с размеченным источником, 12 без ответа и 1 уточнение. Ни один test-запрос не совпадает дословно с заголовком или alias. Это не независимая человеческая выборка.',
      'Параметры приоритета источника и порог ответа выбирались на dev. Test использовался для отчётных сравнений, включая промежуточный прогон; поэтому его следует считать внутренней отложенной проверкой, а не окончательным независимым доказательством качества. Перед сдачей полезен новый набор от студентов.',
      'P@1: релевантность первого результата. P@3: число размеченных релевантных результатов / 3. При одной метке максимум P@3 равен 1/3. Hit@3 показывает наличие правильного результата в тройке. MRR@5 учитывает позицию первого правильного результата в первых пяти.',
      f'Лучший P@1 в сохранённой таблице test: {best["method"]}/{best["preprocessing"]}, {best["p1"]:.3f}; MRR@5 {best["mrr"]:.3f}. Таблица ниже относится к поиску источников без диалоговой фильтрации.',
      'Каждый метод запускается в отдельном процессе. Peak RSS измерен Linux ru_maxrss и включает Python, библиотеки и модели. Время подготовки отделено от времени запросов. Кеш эмбеддингов может ускорять повторное построение; аппаратная среда влияет на результаты.'
    ]),
    ('Ошибки и пределы качества',[
      f'Диалоговая проверка test: совпадение ожидаемого источника либо типа отказа/уточнения в {correct} из {len(held)} случаев. Ответ выдан в {len(answered)} случаях; это не означает, что все его утверждения независимо проверены.',
      'Матрица тем показывает, из какого раздела извлечён первый документ; это proxy, а не матрица истинности ответа. Отдельная матрица решения показывает answered/clarification/abstained. Конкретные ошибки сохранены в retrieval_errors.csv и dialogue_errors.csv.',
      'Разметка релевантности неполная: одно и то же утверждение может встречаться в нескольких карточках. При этом подмена входящей мобильности исходящей или условий иностранцев общими условиями является содержательной ошибкой и требует проверки.',
      'Покрытие официальных тем ограничено 48 карточками. Большая часть исходного датасета не проверена на актуальность. Качество на отложенных вопросах про официальные дополнения нельзя переносить на все 556 исходных FAQ.',
      'Следующий шаг: независимая проверка реальными студентами, несколько допустимых источников на вопрос, дальнейшая очистка конфликтующих сведений и расширение официального корпуса. Изменение модели без измерений не гарантирует улучшение.'
    ]),
    ('SQLite, SQL и требования задания',[
      'Схема содержит 10 таблиц: sources, documents, aliases, keywords, document_keywords, test_cases, relevance, evaluation_runs, predictions, feedback. Связи M:N реализованы отдельными таблицами; включены foreign_keys и индексы.',
      'Корпус, происхождение, метки, ключевые слова и результаты хранятся в SQLite. Прогоны дописываются с UUID и fingerprint данных/реализации. Повторный импорт обновляет записи по стабильным ID, не очищает историю исследований.',
      'В queries.sql — 12 аналитических запросов. Они включают JOIN, GROUP BY/HAVING, EXISTS/IN-подзапросы, CTE, ROW_NUMBER и DENSE_RANK. Все результаты загружаются в Pandas и экспортируются в artifacts/sql.',
      'Проект демонстрирует более пяти функций, list/dict, if/elif/else, циклы, чтение/запись файлов, try/except, модули и стандартную библиотеку. Есть интерактивное консольное меню и Streamlit с фильтрами.',
      'Исходники, данные, README, этот отчёт, презентация и сценарий защиты включены в поставку. GitHub/Moodle требуют действий владельцев аккаунтов. Исключение по размеру корпуса, использование ИИ и фактический вклад не отмечаются согласованными без подтверждения.'
    ]),
    ('Источники и вклад',[
      'Датасет: Arailym-tleubayeva/AITUAdmissionsGuideDataset, Hugging Face. Указание автора и ссылки сохранено. Неоднозначность лицензии описана в THIRD_PARTY_NOTICES.md; некоммерческое использование не отменяет условий правообладателей.',
      'Официальные страницы: astanait.edu.kz/ru/bachelor; /ru/master; /ru/aitu-excellence-test; /ru/academic-mobility-foreign-citizens; /ru/outg-academ-mobility; /ru/officeregistrar; /ru/students-dormitory; /ru/military-department; int.astanait.edu.kz/ru/inc-academ-mobility.',
      'Изучены исходники METUBot (GDG-on-Campus-METU, Apache-2.0), Chatbot-MiNI (Kolo-Naukowe-Data-Science-PW, MIT), TheWerbinator/university-chatbot. Взяты идеи гибридного поиска, reranking и приоритета источников. Чужой код не копировался. Точные ссылки и ревизии сохранены в THIRD_PARTY_NOTICES.md.',
      'Помощь ИИ: проектирование, реализация нового приложения, создание вариантов запросов и разметки, проверки, эксперименты и подготовка материалов. Все это подлежит проверке командой и согласованию правил дисциплины.',
      'Baizhanov Alimzhan: фактический вклад пока не распределён. Zhanbolat Karimzhanov: фактический вклад пока не распределён. Заполнить после самостоятельной работы и проверки, не выдавая предложенные роли за выполненную работу.'
    ])]
    (ROOT/'docs/REPORT.md').write_text('\n\n'.join('# '+title+'\n\n'+'\n\n'.join(paras) for title,paras in sections)+'\n')
    font=Path('/usr/share/fonts/google-noto/NotoSans-Regular.ttf');bold=font.with_name('NotoSans-Bold.ttf')
    if not font.exists():raise RuntimeError('Для PDF нужен Noto Sans; Markdown отчёт уже создан.')
    pdfmetrics.registerFont(TTFont('Body',str(font)));pdfmetrics.registerFont(TTFont('Head',str(bold)))
    body=ParagraphStyle('Body',fontName='Body',fontSize=9.7,leading=14.5,spaceAfter=11,textColor=colors.HexColor('#173536'))
    heading=ParagraphStyle('Head',fontName='Head',fontSize=21,leading=26,spaceAfter=19,textColor=colors.HexColor('#176b67'))
    story=[]
    for i,(title,paragraphs) in enumerate(sections):
        story.append(Paragraph(escape(title),heading))
        for para in paragraphs:story.append(Paragraph(escape(para),body))
        if i==4:
            rows=[['Метод','P@1','MRR@5','мс','RSS МБ']]
            for r in test.itertuples():rows.append([r.method+'/'+r.preprocessing,f'{r.p1:.3f}',f'{r.mrr:.3f}',f'{r.latency_ms:.1f}',f'{r.peak_rss_mb:.0f}'])
            t=Table(rows,colWidths=[180,52,58,60,65]);t.setStyle(TableStyle([('FONTNAME',(0,0),(-1,-1),'Body'),('FONTSIZE',(0,0),(-1,-1),8),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#176b67')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('BOTTOMPADDING',(0,0),(-1,-1),5)]));story.append(t)
        if i==5 and mistakes:
            r=mistakes[0];story.append(Paragraph(escape('Пример ошибки: '+r['query']+' | ожидалось: '+str(r['relevant'])+' | получено: '+str(r['predicted'])+' / '+r['predicted_status']),body))
        if i<len(sections)-1:story.append(PageBreak())
    def footer(canvas,doc):
        canvas.setFont('Body',8);canvas.setFillColor(colors.HexColor('#607875'));canvas.drawString(42,25,'AITU Campus Answers · Final Project · 15.11.2026');canvas.drawRightString(553,25,str(doc.page))
    SimpleDocTemplate(str(ROOT/'deliverables/Report.pdf'),pagesize=(595,842),leftMargin=42,rightMargin=42,topMargin=42,bottomMargin=42).build(story,onFirstPage=footer,onLaterPages=footer)
    print('Written report generated')

if __name__=='__main__':main()
