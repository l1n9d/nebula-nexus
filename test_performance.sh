#!/bin/bash
# Performance Testing Script for Optimized RAG API

API_URL="http://136.119.12.105:8000/api/v1"

echo "=========================================="
echo "🚀 RAG API Performance Test"
echo "=========================================="
echo ""

# Test 1: Cache Miss (First Request)
echo "📊 Test 1: First Request (Cache Miss)"
echo "Query: 'What are transformers in machine learning?'"
echo ""
time curl -X POST "$API_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are transformers in machine learning?",
    "top_k": 3,
    "use_hybrid": true,
    "model": "llama3.2:1b"
  }' 2>&1 | python3 -m json.tool | head -30

echo ""
echo "=========================================="
echo ""

# Wait a bit
sleep 3

# Test 2: Cache Hit (Same Request)
echo "📊 Test 2: Repeat Query (Cache Hit Expected)"
echo "Query: 'What are transformers in machine learning?'"
echo ""
time curl -X POST "$API_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are transformers in machine learning?",
    "top_k": 3,
    "use_hybrid": true,
    "model": "llama3.2:1b"
  }' 2>&1 | python3 -m json.tool | head -30

echo ""
echo "=========================================="
echo ""

# Test 3: BM25 Only (No Embedding)
echo "📊 Test 3: BM25 Only (No Embedding Generation)"
echo "Query: 'attention mechanisms'"
echo ""
time curl -X POST "$API_URL/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "attention mechanisms",
    "top_k": 2,
    "use_hybrid": false,
    "model": "llama3.2:1b"
  }' 2>&1 | python3 -m json.tool | head -30

echo ""
echo "=========================================="
echo ""
echo "✅ Performance Tests Complete!"
echo ""
echo "💡 Tips:"
echo "  - First requests take longer (10-25s expected)"
echo "  - Cached requests should be 5-12s"
echo "  - BM25-only is fastest (8-15s)"
echo "  - Check 'chunks_used' - fewer chunks = faster"
echo ""
echo "📊 Check Redis cache:"
echo "  docker exec -it rag-redis redis-cli KEYS \"*\""
echo ""

