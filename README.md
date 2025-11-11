<div align="center">

# ✨ Nebula Nexus

### AI Research Navigator

*Explore 73,000+ arXiv Papers with Intelligent Hybrid Search*

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenSearch](https://img.shields.io/badge/OpenSearch-2.19-005EB8?style=for-the-badge&logo=opensearch&logoColor=white)](https://opensearch.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)](https://github.com/l1n9d/nebula-nexus)

**A production-grade RAG system powered by OpenSearch, FastAPI, and Llama 3.2**

[Getting Started](#-quick-start) • [Documentation](#-architecture) • [Examples](#-usage-examples) • [Contributing](#-contributing)

</div>

---

## 📖 About Nebula Nexus

**Nebula Nexus** is an advanced AI research navigator that combines the power of hybrid search (BM25 + vector embeddings) with local LLM inference to help you explore academic papers efficiently. Built with production best practices, it demonstrates how to create scalable RAG systems that actually work.

### ✨ Key Features

- **🔍 Hybrid Search Engine** - Combines BM25 keyword search with k-NN vector similarity for superior retrieval
- **🤖 Local LLM Integration** - Uses Ollama (Llama 3.2:1b) for privacy-preserving AI responses
- **⚡ Real-time Streaming** - FastAPI backend with streaming responses for better UX
- **🎨 Modern UI** - Beautiful Gradio interface with custom styling
- **📦 Full Docker Stack** - PostgreSQL, OpenSearch, Redis, Ollama - all containerized
- **🔄 Automated Ingestion** - Airflow DAGs for scheduled paper fetching from arXiv
- **💾 Smart Caching** - Redis caching layer for optimized performance
- **📊 73K+ Papers** - Pre-configured for AI, ML, NLP, and Computer Vision research

---

## 🚀 Quick Start

### **📋 Prerequisites**

- **Docker Desktop** (with Docker Compose v2+)
- **Python 3.12+**
- **UV Package Manager** ([Install Guide](https://docs.astral.sh/uv/getting-started/installation/))
- **8GB+ RAM** and **20GB+ free disk space**

### **⚡ Installation**

```bash
# 1. Clone the repository
git clone https://github.com/l1n9d/nebula-nexus.git
cd nebula-nexus

# 2. Configure environment
cp .env.example .env
# Edit .env if needed - defaults work out of the box

# 3. Install Python dependencies
uv sync

# 4. Start all services (PostgreSQL, OpenSearch, Redis, Ollama, API)
docker compose -f compose.minimal.yml up -d

# 5. Wait for services to initialize (~60 seconds)
sleep 60

# 6. Verify API health
curl http://localhost:8000/api/v1/health

# 7. Start Gradio UI
python3 src/gradio_app.py
```

### **🌐 Access the Application**

- **Gradio UI:** http://localhost:7860
- **API Documentation:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/v1/health

---

## 🏗️ Architecture

### **Tech Stack**

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | FastAPI 0.115+ | REST API with streaming support |
| **Search Engine** | OpenSearch 2.19 | Hybrid BM25 + k-NN vector search |
| **Database** | PostgreSQL 16 | Paper metadata and relationships |
| **Cache** | Redis 7 | API response caching |
| **LLM** | Ollama (Llama 3.2:1b) | Local inference for RAG |
| **Frontend** | Gradio 4.0+ | Interactive web interface |
| **Orchestration** | Airflow 2.10+ | Scheduled paper ingestion |
| **Embeddings** | Sentence Transformers | Vector embeddings for semantic search |

### **System Design**

```
┌─────────────┐
│   Gradio    │  ← User Interface (Port 7860)
│     UI      │
└──────┬──────┘
       │
┌──────▼──────┐
│   FastAPI   │  ← API Layer (Port 8000)
│   Backend   │
└──────┬──────┘
       │
    ┌──┴──────────────────────────────┐
    │                                  │
┌───▼─────┐  ┌──────────┐  ┌─────────▼────┐
│  Redis  │  │PostgreSQL│  │  OpenSearch  │
│  Cache  │  │ Database │  │ (Hybrid BM25 │
│         │  │          │  │  + Vectors)  │
└─────────┘  └──────────┘  └──────────────┘
                                  │
                            ┌─────▼─────┐
                            │  Ollama   │
                            │  LLM      │
                            └───────────┘
```

---

## 📦 Docker Services

The project uses Docker Compose to orchestrate multiple services:

### **Minimal Stack** (`compose.minimal.yml`)
Core services only (~2.8 GB):
- **rag-api** - FastAPI backend (Port 8000)
- **rag-postgres** - PostgreSQL database (Port 5432)
- **rag-opensearch** - Search engine (Port 9200)
- **rag-redis** - Cache layer (Port 6379)
- **rag-ollama** - LLM inference (Port 11434)

### **Full Stack** (`compose.yml`)
Includes monitoring and orchestration (~4.2 GB):
- All minimal services +
- **Airflow** - Workflow orchestration (Port 8080)
- **Langfuse** - LLM observability (Port 3000)
- **ClickHouse** - Analytics database

---

## 📊 Data Ingestion

### **Ingest Papers by Date Range**

```bash
# Ingest papers from arXiv (CS.AI category)
python3 bulk_ingest_by_date.py 20241101 20241107 cs.AI

# Ingest from multiple categories
python3 bulk_ingest_by_date.py 20241101 20241107 cs.AI,cs.LG,cs.CL
```

### **Index Papers into OpenSearch**

```bash
# After ingestion, index all papers for search
python3 index_all_papers.py
```

### **Automated Daily Ingestion**

The project includes Airflow DAGs for scheduled ingestion:

```bash
# Start full stack with Airflow
docker compose up -d

# Access Airflow UI: http://localhost:8080
# Username: admin
# Password: admin (see .env file)
```

---

## 🔍 Usage Examples

### **Using the Gradio Interface**

1. Open http://localhost:7860
2. Enter your research question (e.g., "What are the latest advances in transformer architectures?")
3. Adjust settings:
   - **Context Chunks:** Number of papers to retrieve (1-10)
   - **Hybrid Search:** Enable/disable vector search
   - **LLM Model:** Select model (default: llama3.2:1b)
   - **Categories:** Filter by arXiv categories
4. Click "🚀 Ask AI" and watch the streaming response

### **Using the API**

```bash
# Health check
curl http://localhost:8000/api/v1/health

# Search papers (BM25 only)
curl -X POST http://localhost:8000/api/v1/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "attention mechanisms in transformers",
    "top_k": 5,
    "use_hybrid": false
  }'

# RAG query with streaming
curl -X POST http://localhost:8000/api/v1/ask/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain how attention mechanisms work",
    "top_k": 3,
    "use_hybrid": true,
    "model": "llama3.2:1b"
  }'
```

---

## 🛠️ Development

### **Project Structure**

```
nebula-nexus/
├── src/
│   ├── main.py              # FastAPI application
│   ├── gradio_app.py        # Gradio UI
│   ├── config.py            # Configuration
│   ├── routers/             # API endpoints
│   ├── services/            # Business logic
│   │   ├── opensearch/      # Search service
│   │   ├── ollama/          # LLM service
│   │   ├── embeddings/      # Vector embeddings
│   │   └── cache/           # Redis caching
│   ├── models/              # SQLAlchemy models
│   └── schemas/             # Pydantic schemas
├── airflow/
│   └── dags/                # Data ingestion workflows
├── tests/                   # Unit & integration tests
├── compose.minimal.yml      # Minimal Docker stack
├── compose.yml              # Full Docker stack
├── pyproject.toml           # Python dependencies
└── README.md                # This file
```

### **Running Tests**

```bash
# Install dev dependencies
uv sync --dev

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_config.py
```

### **Code Quality**

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking
mypy src/
```

---

## 🚀 Deployment

### **Local Development**

```bash
docker compose -f compose.minimal.yml up -d
python3 src/gradio_app.py
```

### **GCP VM Deployment**

```bash
# Deploy to new GCP VM
./deploy_to_gcp.sh

# Or restart existing VM
./restart_gcp_vm.sh
```

### **Environment Variables**

Key settings in `.env`:

```bash
# API
APP_VERSION=0.1.0
LOG_LEVEL=INFO

# PostgreSQL
POSTGRES_DATABASE_URL=postgresql://rag_user:rag_password@localhost:5432/rag_db

# OpenSearch
OPENSEARCH_HOST=http://localhost:9200

# Ollama
OLLAMA_HOST=http://localhost:11434
DEFAULT_MODEL=llama3.2:1b

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Optional: Jina AI for embeddings
JINA_API_KEY=your_key_here
```

---

## 📈 Performance

### **Optimizations Implemented**

- ✅ **Gzip Compression** - 30-50% bandwidth reduction
- ✅ **Redis Caching** - 90% faster repeated queries
- ✅ **Database Indexes** - 5x faster metadata queries
- ✅ **Connection Pooling** - 30 concurrent connections
- ✅ **Health Check Caching** - Reduces API overhead
- ✅ **Hybrid Search** - Better relevance than BM25 alone

### **Benchmarks**

| Metric | Value |
|--------|-------|
| **Papers Indexed** | 73,040 |
| **Search Latency** | <100ms (BM25), <500ms (Hybrid) |
| **RAG Response** | ~2-5 seconds (streaming) |
| **Cache Hit Rate** | 85-90% |
| **Memory Usage** | ~3 GB (minimal stack) |

---

## 🎓 Learning Resources

This project demonstrates production RAG system development through:

1. **Infrastructure Setup** - Docker, PostgreSQL, OpenSearch
2. **Data Pipeline** - arXiv API integration, Airflow orchestration
3. **Search Implementation** - BM25 keyword search with filtering
4. **Hybrid Search** - Chunking strategies + vector embeddings
5. **RAG Integration** - Local LLM with streaming responses
6. **Production Features** - Caching, monitoring, optimization

### **Related Blog Posts**

- [The Infrastructure That Powers RAG Systems](https://jamwithai.substack.com/p/the-infrastructure-that-powers-rag)
- [Building Data Ingestion Pipelines for RAG](https://jamwithai.substack.com/p/bringing-your-rag-system-to-life)
- [The Search Foundation Every RAG System Needs](https://jamwithai.substack.com/p/the-search-foundation-every-rag-system)
- [The Chunking Strategy That Makes Hybrid Search Work](https://jamwithai.substack.com/p/the-chunking-strategy-that-makes-hybrid-search-work)

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

### **Development Setup**

```bash
# Clone and setup
git clone https://github.com/l1n9d/nebula-nexus.git
cd nebula-nexus

# Install with dev dependencies
uv sync --dev

# Install pre-commit hooks
pre-commit install

# Run tests
pytest
```

---

## 📝 License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

---

## 🙏 Acknowledgments

- **arXiv** - For providing free access to academic papers
- **OpenSearch** - For powerful hybrid search capabilities
- **Ollama** - For making local LLM inference accessible
- **FastAPI** - For the excellent async Python framework
- **Gradio** - For rapid UI development

---

## 📞 Contact

For questions or feedback, please open an issue on GitHub.

---

<div align="center">
  <p><strong>✨ Built with passion for the AI research community ✨</strong></p>
  <p>⭐ Star this repo if you find it useful! ⭐</p>
</div>
