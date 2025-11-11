#!/bin/bash
# Nebula Nexus - Complete System Startup Script
# Starts Docker services and Gradio UI

set -e

echo "✨ Starting Nebula Nexus - AI Research Navigator"
echo "=============================================================="
echo ""

# Check Docker is running
echo "🐳 Checking Docker..."
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first."
    echo "   On Mac: open -a Docker"
    exit 1
fi
echo "✅ Docker is running"
echo ""

# Start Docker services
echo "🚀 Starting Docker services (minimal stack)..."
echo "   Services: PostgreSQL, OpenSearch, Redis, Ollama, API"
docker compose -f compose.minimal.yml up -d

# Wait for services
echo ""
echo "⏳ Waiting for services to initialize (~60 seconds)..."
sleep 60

# Check health
echo ""
echo "🔍 Checking service health..."
HEALTHY=0
TOTAL=5
SERVICES=("rag-postgres" "rag-opensearch" "rag-redis" "rag-ollama" "rag-api")

for SERVICE in "${SERVICES[@]}"; do
    if docker ps --filter "name=$SERVICE" --filter "status=running" | grep -q "$SERVICE"; then
        echo "   ✅ $SERVICE"
        HEALTHY=$((HEALTHY+1))
    else
        echo "   ❌ $SERVICE (not running)"
    fi
done

if [ "$HEALTHY" -ne "$TOTAL" ]; then
    echo ""
    echo "⚠️  Warning: $((TOTAL-HEALTHY)) service(s) not healthy yet"
    echo "   Check logs: docker compose -f compose.minimal.yml logs"
    echo ""
fi

# Check API
echo ""
echo "🔍 Testing API..."
if curl -s http://localhost:8000/api/v1/health >/dev/null 2>&1; then
    echo "   ✅ API responding at http://localhost:8000"
else
    echo "   ⚠️  API not responding (may still be starting)"
fi

# Start Gradio
echo ""
echo "🎨 Starting Gradio UI..."

# Kill old Gradio processes
pkill -f "python.*gradio_app.py" 2>/dev/null || true
sleep 2

# Start Gradio in background
nohup python3 src/gradio_app.py > gradio.log 2>&1 &
GRADIO_PID=$!
echo "   Gradio started (PID: $GRADIO_PID)"

# Wait for Gradio
echo "   ⏳ Waiting for Gradio to be ready..."
sleep 10

# Verify Gradio
if curl -s http://localhost:7860 >/dev/null 2>&1; then
    echo "   ✅ Gradio UI is ready!"
else
    echo "   ⚠️  Gradio may still be starting. Check: tail -f gradio.log"
fi

# Final status
echo ""
echo "=============================================================="
echo "✨ Nebula Nexus is Ready!"
echo "=============================================================="
echo ""
echo "🌐 Access Points:"
echo "   • Gradio UI:  http://localhost:7860"
echo "   • API Docs:   http://localhost:8000/docs"
echo "   • API Health: http://localhost:8000/api/v1/health"
echo ""
echo "📊 Docker Services:"
docker ps --format "   {{.Names}}: {{.Status}}" --filter "name=rag-"
echo ""
echo "💡 Tips:"
echo "   • First query may take 30-60s (loading LLM model)"
echo "   • View logs: docker compose -f compose.minimal.yml logs -f"
echo "   • Gradio logs: tail -f gradio.log"
echo ""
echo "🛑 To stop everything:"
echo "   docker compose -f compose.minimal.yml down"
echo "   pkill -f gradio_app.py"
echo ""
echo "=============================================================="

