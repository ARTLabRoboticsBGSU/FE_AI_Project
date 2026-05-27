FastAPI scaffold for ChatISA

Quick start (inside project venv):

1. Install dependencies:

```bash
.venv/bin/python -m pip install -r requirements.txt
# or install specific deps
.venv/bin/python -m pip install fastapi uvicorn[standard]
```

2. Run the API server:

```bash
.venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

3. Example requests:

POST /chat
```bash
curl -s -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"Hello"}]}'
```

GET /chat/history
```bash
curl http://127.0.0.1:8000/chat/history
```

Instructor analytics example:
```bash
curl http://127.0.0.1:8000/analytics-summary
```

Notes:
- This scaffold uses in-memory stores for demo only. Replace with a persistent DB and background workers for production.
- Secure endpoints with auth (JWT/API Key) before exposing to the network.
