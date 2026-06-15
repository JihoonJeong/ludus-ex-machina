FROM python:3.12-slim

WORKDIR /app

COPY requirements-server.txt requirements.txt requirements-gcs.txt ./
RUN pip install --no-cache-dir -r requirements-server.txt -r requirements.txt -r requirements-gcs.txt

# Host location (a): the hosted server runs the Orchestrator + game engines
# for cross-machine matches, so the image must carry the engine/orchestrator
# code + data, not just server/. The local run_match.py path is unaffected.
COPY server/ server/
COPY lxm/ lxm/
COPY games/ games/
COPY PROTOCOL_v0.2.md ./

EXPOSE 8080

CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8080"]
