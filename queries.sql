-- name: corpus_by_source
SELECT s.kind,COUNT(*) AS cards,COUNT(DISTINCT s.url) AS sources FROM documents d JOIN sources s ON s.id=d.source_id GROUP BY s.kind;
-- name: categories_with_many_cards
SELECT category,COUNT(*) AS cards FROM documents GROUP BY category HAVING COUNT(*)>=3 ORDER BY cards DESC;
-- name: keyword_reach
SELECT k.word,COUNT(*) AS cards FROM keywords k JOIN document_keywords dk ON dk.keyword_id=k.id GROUP BY k.word HAVING COUNT(*)>2 ORDER BY cards DESC LIMIT 20;
-- name: latest_method_results
WITH ranked AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY method,preprocessing,split ORDER BY created_at DESC,id DESC) AS rn FROM evaluation_runs) SELECT method,preprocessing,split,p1,p3,mrr,hit3,latency_ms,peak_rss_mb FROM ranked WHERE rn=1;
-- name: ranking_errors
SELECT t.query,p.document_id,d.question AS retrieved FROM predictions p JOIN test_cases t ON t.id=p.case_id JOIN documents d ON d.id=p.document_id WHERE p.rank=1 AND NOT EXISTS (SELECT 1 FROM relevance r WHERE r.case_id=p.case_id AND r.document_id=p.document_id) LIMIT 30;
-- name: best_methods
WITH latest AS (SELECT *,ROW_NUMBER() OVER(PARTITION BY method,preprocessing ORDER BY created_at DESC,id DESC) rn FROM evaluation_runs WHERE split='test') SELECT method,preprocessing,p1,mrr,DENSE_RANK() OVER(ORDER BY mrr DESC) AS place FROM latest WHERE rn=1;
-- name: aliases_per_document
SELECT d.id,d.question,COUNT(a.id) AS variants FROM documents d LEFT JOIN aliases a ON a.document_id=d.id GROUP BY d.id,d.question ORDER BY variants DESC LIMIT 20;
-- name: coverage_by_level
SELECT level,audience,COUNT(*) AS cards,SUM(CASE WHEN status='unverified' THEN 1 ELSE 0 END) AS unverified FROM documents GROUP BY level,audience;
-- name: test_coverage
SELECT t.split,t.expected_status,COUNT(DISTINCT t.id) AS questions,COUNT(r.document_id) AS labels FROM test_cases t LEFT JOIN relevance r ON r.case_id=t.id GROUP BY t.split,t.expected_status;
-- name: source_ranking_frequency
SELECT s.kind,s.url,COUNT(*) AS top_results FROM predictions p JOIN documents d ON d.id=p.document_id JOIN sources s ON s.id=d.source_id WHERE p.rank=1 GROUP BY s.id,s.kind,s.url ORDER BY top_results DESC;
-- name: source_unreviewed
SELECT url FROM sources WHERE id IN (SELECT DISTINCT source_id FROM documents WHERE status='unverified');
-- name: feedback_summary
SELECT d.id,d.question,COUNT(f.id) AS votes,AVG(f.helpful) AS positive_share FROM documents d JOIN feedback f ON f.document_id=d.id GROUP BY d.id,d.question HAVING COUNT(f.id)>0;
