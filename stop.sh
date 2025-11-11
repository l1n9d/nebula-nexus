#!/bin/bash
# Nebula Nexus - Stop All Services

echo "🛑 Stopping Nebula Nexus..."
echo "=============================================================="
echo ""

# Stop Gradio
echo "🎨 Stopping Gradio UI..."
pkill -f "python.*gradio_app.py" 2>/dev/null && echo "   ✅ Gradio stopped" || echo "   ℹ️  Gradio was not running"

# Stop Docker services
echo ""
echo "🐳 Stopping Docker services..."
docker compose -f compose.minimal.yml down

echo ""
echo "=============================================================="
echo "✅ All services stopped"
echo "=============================================================="
echo ""
echo "💡 To restart: ./start.sh"
echo ""

