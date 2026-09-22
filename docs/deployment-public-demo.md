# Public recorded demo deployment

Project Sentinel — AI-Powered Production Incident Investigation & Remediation Platform.

The default deployment contains only frontend files, a read-only FastAPI server and
sanitized historical records. PostgreSQL, Redis, Kafka, Jaeger, Fault Lab and the live
provider runtime are not part of this image. No API key is required.

## Local / future server startup

```sh
docker compose up -d --build
```

Open http://localhost:18082. The first build downloads Python packages. The default
port binds loopback. The `.env` file is optional for recorded mode; copying
`.env.example` is useful for port/host settings, not for credentials.

For a future host named `sentinel.example.com`, set
`DEMO_ALLOWED_HOSTS=sentinel.example.com,localhost,127.0.0.1,sentinel-demo`, keep
`PUBLIC_DEMO_MODE=true`, and build the same demo image. Place a TLS reverse proxy in
front of loopback port 18082. Terminate TLS there, pass the correct Host, set request
size/rate/time limits and monitor server errors. Example nginx location:

```nginx
location / {
    proxy_pass http://127.0.0.1:18082;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 16k;
}
```

Provision TLS through the host's certificate tooling. No domain, server or paid
service was purchased or deployed during Phase 5. This is a prepared deployment
path, not a claim of an existing public URL.

## Enforced boundary

- The public image copies only `sentinel/public_demo.py` and the empty package
  initializer, not the DB/provider/tool/runtime modules. It receives no secrets.
- Every non-GET/HEAD request returns 403 before routing. Unknown tool/config/upload
  endpoints do not exist. `/live.html` is denied.
- Default container is non-root, filesystem read-only, capabilities dropped and
  resource limited. It has no database credentials, volumes or Docker socket.
- Responses use restrictive CSP, no permissive CORS and a Host allowlist. Raw
  observations are escaped as text; documents are a filename allowlist.
- Public data integrity is checked at startup against its manifest. This detects
  accidental edits; administrators can still modify both data and manifest.

No API alone proves full security. Apply OS/container updates, TLS, monitoring,
backup of the published artifact and rate limits before internet exposure. Reassess
dependency vulnerabilities at deployment time. The limited tests do not certify
protection against arbitrary server compromise or denial of service.

## Explicit local Live mode

Use `compose.live.yaml` only on a local trusted machine. Copy `.env.example` to `.env`,
configure `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY`, then explicitly set
`LIVE_AI_ENABLED=true`. Start `docker compose -f compose.live.yaml up -d --build`.
The workspace is http://localhost:18083/live.html. Live mode incurs model charges and
enables real fault controls. Default false disables controls, detector dispatch and
automatic checkpoint resume. Do not expose this full stack to the internet.

Recorded and Live use different Compose project names and ports. Stop only the
project you intend with its matching compose file. Never remove volumes to switch
modes. Existing Phase 4 volumes and frozen images can remain available locally.
