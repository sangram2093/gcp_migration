# ServiceNow MCP SSE Deployment (Cloud Run)

This guide shows how to run the ServiceNow MCP server in SSE mode, deploy it to
Cloud Run, and connect MCP clients (including IDE agents) over HTTP.

## What SSE Mode Provides

- SSE stream endpoint: `GET /sse`
- Message endpoint: `POST /messages/`
- Session IDs are generated per SSE connection and are kept in memory.
- The SSE server in this repo uses **basic auth only** (username/password from
  environment variables).

## Prerequisites

- Python 3.11+
- ServiceNow instance credentials
- GCP project with Cloud Run enabled (for deployment)

## Environment Variables (SSE Server)

Required:
- `SERVICENOW_INSTANCE_URL`
- `SERVICENOW_USERNAME`
- `SERVICENOW_PASSWORD`

Optional:
- `MCP_TOOL_PACKAGE` (defaults to `full`; see `config/tool_packages.yaml`)

## Local SSE Smoke Test (curl)

Start the server:
```bash
export SERVICENOW_INSTANCE_URL="https://your-instance.service-now.com"
export SERVICENOW_USERNAME="your-username"
export SERVICENOW_PASSWORD="your-password"

servicenow-mcp-sse --host=127.0.0.1 --port=8080
```

Open the SSE stream (keep this terminal open):
```bash
curl -N -H "Accept: text/event-stream" http://127.0.0.1:8080/sse
```

You will receive an `endpoint` event like:
```
event: endpoint
data: /messages/?session_id=9f3b1c2d4e5f...
```

Use that exact path for all POSTs. Each POST must contain a **single** JSON-RPC
message (no batch arrays).

Initialize:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"1.0","capabilities":{},"clientInfo":{"name":"curl-client","version":"1.0"}}}' \
  "http://127.0.0.1:8080/messages/?session_id=YOUR_SESSION_ID"
```

Notify initialized (required before any other request):
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}' \
  "http://127.0.0.1:8080/messages/?session_id=YOUR_SESSION_ID"
```

List tools:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  "http://127.0.0.1:8080/messages/?session_id=YOUR_SESSION_ID"
```

Tool results and server responses appear on the SSE stream terminal as
`event: message`.

## Deploy to Cloud Run

This repo ships with a `Dockerfile` that starts the SSE server on port 8080.
Cloud Run can deploy it directly.

Build and push the image:
```bash
gcloud config set project YOUR_PROJECT_ID
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/servicenow-mcp
```

Deploy:
```bash
gcloud run deploy servicenow-mcp \
  --image gcr.io/YOUR_PROJECT_ID/servicenow-mcp \
  --region YOUR_REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars SERVICENOW_INSTANCE_URL=https://your-instance.service-now.com,SERVICENOW_USERNAME=your-username,SERVICENOW_PASSWORD=your-password \
  --min-instances 1 \
  --max-instances 1 \
  --timeout 3600
```

### Use Secret Manager (recommended)

Store credentials in Secret Manager and map them to environment variables:
```bash
printf "your-username" | gcloud secrets create SERVICENOW_USERNAME --data-file=-
printf "your-password" | gcloud secrets create SERVICENOW_PASSWORD --data-file=-
printf "https://your-instance.service-now.com" | gcloud secrets create SERVICENOW_INSTANCE_URL --data-file=-
```

Then deploy with secret bindings:
```bash
gcloud run deploy servicenow-mcp \
  --image gcr.io/YOUR_PROJECT_ID/servicenow-mcp \
  --region YOUR_REGION \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --set-secrets SERVICENOW_INSTANCE_URL=SERVICENOW_INSTANCE_URL:latest,SERVICENOW_USERNAME=SERVICENOW_USERNAME:latest,SERVICENOW_PASSWORD=SERVICENOW_PASSWORD:latest \
  --min-instances 1 \
  --max-instances 1 \
  --timeout 3600
```

## Cloud Run Operational Notes

- **Single instance is required** for reliable SSE sessions. Session state is
  stored in memory. If Cloud Run scales to multiple instances, `POST /messages/`
  can hit a different instance and return `404 Could not find session`. Keep
  `--max-instances 1` unless you implement shared session storage.
- **Long-lived connections**: SSE keeps a request open. Increase the request
  timeout (example uses 3600 seconds). Clients should reconnect if the stream
  closes.
- **Security**: Expose the service only to trusted clients. If you need
  authentication, prefer Cloud Run IAM or an API gateway that supports SSE.

## Connect an MCP Client (Cline or Other)

MCP SSE flow (client responsibilities):
1. Open `GET https://YOUR_RUN_URL/sse`
2. Parse the `event: endpoint` data (e.g., `/messages/?session_id=...`)
3. `POST` an `initialize` request
4. Wait for the initialize response on the SSE stream
5. `POST` a `notifications/initialized` message
6. Call tools with `tools/list` and `tools/call`

Client configuration varies by tool. If your MCP client asks for a server URL,
use the Cloud Run base URL and SSE endpoint (`/sse`) it expects. Always follow
the exact `endpoint` path returned by the SSE stream for message posts.
