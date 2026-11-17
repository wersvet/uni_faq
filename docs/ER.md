# ER-диаграмма SQLite

```mermaid
erDiagram
    sources ||--o{ documents : source_id
    documents ||--o{ aliases : document_id
    documents ||--o{ document_keywords : document_id
    keywords ||--o{ document_keywords : keyword_id
    test_cases ||--o{ relevance : case_id
    documents ||--o{ relevance : document_id
    evaluation_runs ||--o{ predictions : run_id
    test_cases ||--o{ predictions : case_id
    documents ||--o{ predictions : document_id
    documents ||--o{ feedback : document_id
    sources {
        INTEGER id PK
        TEXT url UK
        TEXT kind
        TEXT checked_at
    }
    documents {
        TEXT id PK
        INTEGER source_id FK
        TEXT question
        TEXT answer
        TEXT category
        TEXT level
        TEXT audience
        TEXT intent
        TEXT valid_year
        TEXT status
    }
    aliases {
        INTEGER id PK
        TEXT document_id FK
        TEXT text
    }
    keywords {
        INTEGER id PK
        TEXT word UK
    }
    document_keywords {
        TEXT document_id PK,FK
        INTEGER keyword_id PK,FK
    }
    test_cases {
        TEXT id PK
        TEXT query
        TEXT split
        TEXT expected_status
        TEXT topic
    }
    relevance {
        TEXT case_id PK,FK
        TEXT document_id PK,FK
    }
    evaluation_runs {
        TEXT id PK
        TEXT method
        TEXT preprocessing
        TEXT fingerprint
        REAL p1
        REAL p3
        REAL mrr
        REAL latency_ms
        REAL peak_rss_mb
    }
    predictions {
        TEXT run_id PK,FK
        TEXT case_id PK,FK
        INTEGER rank PK
        TEXT document_id FK
        REAL score
    }
    feedback {
        INTEGER id PK
        TEXT document_id FK
        INTEGER helpful
    }
```

Всего 10 таблиц. Связи M:N: документы–ключевые слова и вопросы оценки–релевантные документы. Все подключения включают foreign_keys; повторный импорт обновляет записи по стабильным ID. История оценок дописывается с UUID, не заменяется. Текст пользовательской переписки в SQLite не записывается; feedback хранит только ID источника и оценку. `queries.sql` содержит 12 запросов с JOIN, GROUP BY/HAVING, CTE, подзапросами и оконными функциями; `tools/analyze.py` загружает их результаты в Pandas и CSV.
