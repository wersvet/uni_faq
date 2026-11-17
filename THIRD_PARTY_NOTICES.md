# Источники, лицензии и принятые подходы

Приложение написано заново для этого задания. Оно использует исходный учебный датасет и ранее собранные короткие карточки источников. Код прежнего приложения не является основой новой реализации. Код сторонних ботов не копировался и не исполнялся; использованы архитектурные идеи.

## Данные

- Arailym-tleubayeva, AITUAdmissionsGuideDataset: https://huggingface.co/datasets/Arailym-tleubayeva/AITUAdmissionsGuideDataset . Исходный CSV: https://huggingface.co/datasets/Arailym-tleubayeva/AITUAdmissionsGuideDataset/resolve/main/QA_addmissionAitu.csv . 608 строк; максимальный индекс 704 не равен числу записей. В карточке метаданных указана CC BY 4.0; ранее в описании встречалась CC BY-NC 4.0. До стороннего распространения следует уточнить неоднозначность у автора. Авторство и ссылка сохранены; учебный некоммерческий характер не отменяет условий лицензии.
- Официальные страницы AITU перечислены в поле `url` корпуса. Короткие пересказы с датами просмотра 9–10 ноября 2026 сохранены отдельно от исходного датасета. Полные страницы не перераспространяются. Дата просмотра не означает одобрение университетом или проверку человеком.
- 96 поисковых вариантов и 122 вопроса оценки составлены с помощью ИИ. Они не являются реальными обращениями студентов. Разметка требует человеческой проверки.

## Открытые университетские проекты

1. METUBot: https://github.com/GDG-on-Campus-METU/metubot . Просмотренная ревизия `de46cf5e7cdf3996e27264b768a4347fe56f02bf`. Apache-2.0. В `v1.6.1/retrieval.py` сочетаются BM25 и векторный поиск; `qa_chain_builder.py` формирует ответ по найденным документам. В новом проекте BM25 реализован самостоятельно, генеративная модель для основного режима не нужна.
2. Chatbot-MiNI: https://github.com/Kolo-Naukowe-Data-Science-PW/Chatbot-MiNI . Ревизия `6c4db046cfe9a7b300f584b6fbf727d4a27d4e01`. MIT. В `src/api/retrieval.py` применяются RRF и multilingual cross-encoder. Идея двухэтапного поиска адаптирована для небольшой локальной SQLite-базы, без Qdrant и внешнего API.
3. TheWerbinator/university-chatbot: https://github.com/TheWerbinator/university-chatbot . Ревизия `d84b7d7e0b2911ee6084bca42f874c0cfa96a1e6`. В просмотренном дереве не найден отдельный LICENSE; разрешение на копирование кода не предполагается. Изучена идея приоритета авторитетного источника отдельно от оценки релевантности. Исходники не копируются.
4. Retrieve & Re-Rank, Sentence Transformers: https://sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html . Обоснование двухэтапного извлечения и проверки кандидатов.

## Модели и библиотеки

- `intfloat/multilingual-e5-base`: https://huggingface.co/intfloat/multilingual-e5-base . MIT, ревизия закреплена в `faq/config.py`. Префиксы query/passage (в коде: `query:`, `passage:`), нормированные векторы, локальный CPU. Модель не дообучается.
- `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`: https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 . Apache-2.0. Используется для пар вопрос–документ. Оценка логита не трактуется как вероятность.
- spaCy: https://spacy.io/models/ru . Используется Russian blank pipeline + компонент lemmatizer в режиме pymorphy3; это настоящая spaCy-лемматизация без загрузки модели NER. NLTK Snowball применяется для stemming. Сравнение сохраняется в CSV.
- Версии прямых зависимостей перечислены в `requirements.txt`, тестовых — в `requirements-dev.txt`. Веса загружаются из официальных репозиториев по закреплённым ревизиям, `trust_remote_code=False`.

Генерация иллюстраций, чужие логотипы и тексты вузов не используются как собственные. При публикации необходимо сохранить этот файл и атрибуцию данных.
