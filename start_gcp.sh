#!/bin/bash
# Start Nebula Nexus on GCP VM

set -e

VM_NAME="arxiv-rag-vm"
ZONE="us-central1-a"
PROJECT_ID="gen-lang-client-0402375053"

echo "✨ Starting Nebula Nexus on GCP VM"
echo "=============================================================="
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Check VM status
echo "📊 Checking VM status..."
STATUS=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(status)' 2>/dev/null || echo "NOT_FOUND")

if [ "$STATUS" = "NOT_FOUND" ]; then
    echo "❌ VM not found! Please create it first."
    exit 1
fi

# Start VM if not running
if [ "$STATUS" != "RUNNING" ]; then
    echo "🔄 Starting VM..."
    gcloud compute instances start $VM_NAME --zone=$ZONE
    echo "⏳ Waiting for VM to boot (30 seconds)..."
    sleep 30
fi

# Get external IP
EXTERNAL_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
echo "✅ VM is running at: $EXTERNAL_IP"
echo ""

# Start services on VM
echo "🐳 Starting Docker services on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd ~/arxiv-rag || cd ~/nebula-nexus || {
        echo '❌ Project directory not found on VM'
        exit 1
    }
    
    echo '📦 Starting Docker Compose...'
    /usr/bin/docker-compose -f compose.minimal.yml down 2>/dev/null || true
    /usr/bin/docker-compose -f compose.minimal.yml up -d
    
    echo '⏳ Waiting for services to initialize (60 seconds)...'
    sleep 60
    
    echo '🔍 Checking service health...'
    docker ps --format 'table {{.Names}}\t{{.Status}}'
"

echo ""
echo "🎨 Starting Gradio UI on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="
    cd ~/arxiv-rag || cd ~/nebula-nexus
    
    # Kill old Gradio processes
    pkill -f 'python.*gradio_app.py' 2>/dev/null || true
    sleep 2
    
    # Start Gradio
    nohup python3 src/gradio_app.py > gradio.log 2>&1 &
    
    echo '⏳ Waiting for Gradio to start (10 seconds)...'
    sleep 10
    
    echo '✅ Gradio started'
"

echo ""
echo "=============================================================="
echo "✨ Nebula Nexus is Ready on GCP!"
echo "=============================================================="
echo ""
echo "🌐 Access Points:"
echo "   • Gradio UI:  http://$EXTERNAL_IP:7860"
echo "   • API Docs:   http://$EXTERNAL_IP:8000/docs"
echo "   • API Health: http://$EXTERNAL_IP:8000/api/v1/health"
echo ""
echo "📊 Check Status:"
echo "   gcloud compute ssh $VM_NAME --zone=$ZONE"
echo "   docker ps"
echo "   tail -f gradio.log"
echo ""
echo "🛑 To Stop:"
echo "   gcloud compute instances stop $VM_NAME --zone=$ZONE"
echo ""
echo "=============================================================="

