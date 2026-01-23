# AI Assistant Server

FastAPI server for AI Assistant integration, providing a REST API for frontend communication.

## Features

- **Inference**: Executes queries using AI Assistant with RAG
- **History**: Manages conversation history
- **Health Check**: Monitors server and AI Assistant status
- **CORS**: Configured for frontend communication

## Endpoints

### GET /
- **Description**: Root endpoint to verify if the server is working
- **Response**: Server status

### GET /health
- **Description**: Complete health check of server and AI Assistant
- **Response**: System health status

### POST /inference
- **Description**: Executes inference using AI Assistant
- **Body**:
  ```json
  {
    "query": "Your question here",
    "search_db": true,
    "use_history": true
  }
  ```
- **Response**:
  ```json
  {
    "answer": "AI Assistant response",
    "history_sources": [{"source": "document.pdf", "page": 1}]
  }
  ```

### POST /clear-history
- **Description**: Clears message history
- **Response**: Clear confirmation

### GET /history
- **Description**: Returns current message history
- **Response**: History and sources used

## Configuration

The server is configured through environment variables:

- `EMBEDDING_MODEL`: Embedding model (default: qwen3-embedding:latest)
- `INFERENCE_MODEL`: Inference model (default: gpt-oss:120b)
- `PERSIST_PATH`: Path to persist ChromaDB data
- `COLLECTION_NAME`: Collection name in ChromaDB

## Execution

### Local

**Importante:** Execute os comandos a partir da raiz do projeto (`ai-apps-5g`), não de dentro de `ihm/server`.

#### Opção 1: Usando Python como módulo (recomendado)
```bash
# A partir da raiz do projeto
cd /path/to/ai-apps-5g
pip install -r ihm/server/requirements.txt
python -m ihm.server.main
```

#### Opção 2: Usando uvicorn diretamente
```bash
# A partir da raiz do projeto
cd /path/to/ai-apps-5g
pip install -r ihm/server/requirements.txt
uvicorn ihm.server.modules.app:app --reload
```

#### Opção 3: Executando main.py diretamente (requer estar na raiz)
```bash
# A partir da raiz do projeto
cd /path/to/ai-apps-5g
pip install -r ihm/server/requirements.txt
python ihm/server/main.py
```

O servidor estará disponível em `http://localhost:8000` (ou na porta configurada no `config.env`)
