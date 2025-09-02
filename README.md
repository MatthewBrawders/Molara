# Molara – AI-Powered Literature Reader

Molara is a full-stack **Retrieval-Augmented Generation (RAG)** system that ingests scientific literature and allows users to query and explore complex topics using natural language.  
It combines **FastAPI**, **PostgreSQL with pgvector**, **Sentence-Transformers**, and **Ollama** for local LLM inference, with a **React frontend** for interaction and **Docker Compose** + **NGINX** for deployment.

---

## Features
- **Literature Ingestion** – Chunk and embed scientific documents using [Sentence-Transformers](https://www.sbert.net/).  
- **Vector Search** – Store embeddings in PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension.  
- **RAG Querying** – Retrieve relevant chunks and enhance answers with Ollama-powered local LLM inference.  
- **FastAPI Backend** – Modular API for ingestion, querying, and retrieval.  
- **React Frontend** – Sleek interface for natural language queries.  
- **Dockerized Deployment** – Orchestrated with Docker Compose and served via NGINX.  
- **Developer Script (`./dev`)** – Unified commands for building, running, and interacting with the system.  

---

## Tech Stack
- **Backend**: FastAPI, Uvicorn, Pydantic, httpx  
- **Database**: PostgreSQL + pgvector  
- **ML/AI**: Sentence-Transformers, Torch, Ollama (local LLM inference)  
- **Frontend**: React + Vite  
- **Deployment**: Docker, Docker Compose, NGINX  

---

## Project Structure
```
.
├── backend/                     # FastAPI backend
│   ├── Dockerfile
│   ├── main.py                  # ASGI entrypoint
│   ├── db.py                    # DB connection
│   ├── embeddings.py            # Embedding + vector logic
│   ├── initdb/                  # Mounted into Postgres init
│   ├── migrations/              # SQL migration files
│   ├── requirements.txt
│   └── .env                     # Backend config (GEN_MODEL, DB, etc.)
│
├── books/                       # Example documents
│   └── kinase_handbook.txt
│
├── database/                    
│   └── seeds/                   # Seed files (sample DB data)
│
├── frontend/                    # React (Vite) SPA
│
├── nginx/                       # Reverse proxy config
│   └── nginx.conf
│
├── dev                          # Developer helper script
├── docker-compose.yml           # Orchestrates all services
└── README.md                    # You are here
```

---

## Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/your-username/molara.git
cd molara
```

### 2. Ensure Docker Desktop is installed and running

- [Install Docker Desktop](https://www.docker.com/products/docker-desktop) if not already installed.  
- Keep it running in the background.  

### 3. Configure environment variables
Edit `backend/.env` with your preferred models and database settings:

```bash
# Embedding model 
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384

# pgvector query tuning
IVFFLAT_PROBES=10

# FastAPI / Uvicorn settings
HOST=0.0.0.0
PORT=8000

# Ollama model to use
GEN_MODEL=deepseek-r1:7b
```

For frontend (`frontend/.env`):
```bash
VITE_API_BASE_URL=/api
```

### 4. Use the `./dev` script
The `dev` script wraps Docker Compose and adds extra commands.

#### Start everything
```bash
./dev up
```

#### Stop everything
```bash
./dev down
```

#### Restart
```bash
./dev restart
```

#### Check health
```bash
./dev health
```

#### Run a RAG query
```bash
./dev query "What are receptor tyrosine kinases?" 5
```

#### Add a book
```bash
./dev addbook ./books/kinase_handbook.txt "Kinase Handbook"
```

---

## Access the App
- Frontend → [http://localhost](http://localhost)  
- API → [http://localhost/api](http://localhost/api)  

---

With this setup you no longer run `docker compose up` directly — always use `./dev up` (or `restart`, `query`, `addbook`, etc.) so environment variables and health checks are handled for you.  
