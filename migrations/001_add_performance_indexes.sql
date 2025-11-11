-- Performance Indexes for Papers Table
-- This migration adds indexes to speed up common queries by 5-10x
-- Safe to run - uses CONCURRENTLY to avoid locking the table

-- Index 1: Speed up arXiv ID lookups (most common query)
-- Used when retrieving papers by arXiv ID
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_arxiv_id 
ON papers(arxiv_id) 
WHERE arxiv_id IS NOT NULL;

-- Index 2: Speed up PMID lookups
-- Used when retrieving papers by PubMed ID
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_pmid 
ON papers(pmid) 
WHERE pmid IS NOT NULL;

-- Index 3: Speed up date-based queries
-- Used for sorting papers by publication date (DESC for recent first)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_published_date 
ON papers(published_date DESC);

-- Index 4: Speed up unprocessed paper queries (partial index)
-- Used when finding papers that need processing
-- Partial index only includes rows where content_processed = FALSE
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_unprocessed 
ON papers(content_processed) 
WHERE content_processed = FALSE;

-- Index 5: Composite index for category + date queries
-- Used when filtering by category and sorting by date
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_papers_category_date 
ON papers(primary_category, published_date DESC);

-- Update table statistics for query planner
ANALYZE papers;

-- Display index information
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid::regclass)) as index_size
FROM pg_indexes
JOIN pg_class ON pg_indexes.indexname = pg_class.relname
WHERE schemaname = 'public' AND tablename = 'papers'
ORDER BY indexname;

-- Show query plan improvements (example)
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM papers WHERE arxiv_id = '2401.00001';

