#!/bin/bash
# Start the RAG system with minimal services (saves ~1.4 GB memory)

echo "🚀 Starting RAG System in MINIMAL MODE"
echo "=============================================================="
echo "This will save ~1.4 GB memory by disabling:"
echo "  • Airflow (paper ingestion pipeline)"
echo "  • ClickHouse + Langfuse (observability)"
echo "  • OpenSearch Dashboards (search visualization)"
echo ""
echo "Core services that WILL run:"
echo "  ✅ API (FastAPI backend)"
echo "  ✅ OpenSearch (search engine)"
echo "  ✅ PostgreSQL (metadata storage)"
echo "  ✅ Redis (caching)"
echo "  ✅ Ollama (LLM server)"
echo "=============================================================="
echo ""

# Stop any running containers
echo "🧹 Stopping existing containers..."
docker compose down 2>/dev/null || true
docker compose -f compose.minimal.yml down 2>/dev/null || true

# Start minimal services
echo ""
echo "🚀 Starting core services..."
docker compose -f compose.minimal.yml up -d

# Wait for services to be healthy
echo ""
echo "⏳ Waiting for services to become healthy (this may take 1-2 minutes)..."
sleep 30

# Check health
echo ""
echo "🔍 Checking service health..."
SERVICES=("rag-postgres" "rag-opensearch" "rag-redis" "rag-ollama" "rag-api")
HEALTHY=0

for SERVICE in "${SERVICES[@]}"; do
    STATUS=$(docker inspect --format='{{.State.Health.Status}}' "$SERVICE" 2>/dev/null || echo "not_running")
    if [ "$STATUS" == "healthy" ]; then
        echo "  ✅ $SERVICE is healthy"
        HEALTHY=$((HEALTHY+1))
    else
        echo "  ⏳ $SERVICE is $STATUS (check: docker logs $SERVICE)"
    fi
done

echo ""
if [ "$HEALTHY" -eq "${#SERVICES[@]}" ]; then
    echo "🎉 All core services are running!"
else
    echo "⚠️  Some services are still starting. Wait 30 seconds and check:"
    echo "   docker ps"
fi

# Check if Ollama model is pulled
echo ""
echo "🔍 Checking if LLM model is available..."
MODEL_CHECK=$(docker exec rag-ollama ollama list 2>/dev/null | grep tinyllama || echo "not_found")
if [ "$MODEL_CHECK" == "not_found" ]; then
    echo "⚠️  TinyLlama model not found. Pulling now (this is a one-time ~637 MB download)..."
    docker exec rag-ollama ollama pull tinyllama:1.1b
    echo "✅ Model pulled successfully"
else
    echo "✅ TinyLlama model is ready"
fi

echo ""
echo "=============================================================="
echo "✅ MINIMAL RAG SYSTEM IS READY!"
echo "=============================================================="
echo "📊 Expected memory usage: ~2.8 GB (vs 4.2 GB for full system)"
echo ""
echo "🌐 Access the system:"
echo "  • API:          http://localhost:8000/docs"
echo "  • Health Check: http://localhost:8000/api/v1/health"
echo ""
echo "🎨 To start the Gradio UI:"
echo "  ./run_gradio.sh"
echo ""
echo "⚠️  Note: Without Airflow, you'll need to manually ingest papers"
echo "   See notebooks/week2/week2_arxiv_integration.ipynb for examples"
echo ""
echo "🛑 To stop: docker compose -f compose.minimal.yml down"
echo "=============================================================="



