import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RUNS_ROOT = Path("artifacts/abm_runs")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/metrics.json"):
            payload = load_metrics(self.server.run_id)
            if payload is None:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"missing metrics")
                return
            data = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path == "/":
            html = build_html()
            data = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def build_html() -> str:
    return """<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>ABM Agent Metrics</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 24px; }
      pre { background: #f6f6f6; padding: 16px; }
    </style>
  </head>
  <body>
    <h1>ABM Agent Metrics</h1>
    <pre id="metrics">Loading...</pre>
    <script>
      async function refresh() {
        const res = await fetch('/metrics.json');
        if (!res.ok) {
          document.getElementById('metrics').textContent = 'missing metrics';
          return;
        }
        const data = await res.json();
        document.getElementById('metrics').textContent = JSON.stringify(data, null, 2);
      }
      refresh();
      setInterval(refresh, 1000);
    </script>
  </body>
</html>"""


def load_metrics(run_id: str):
    run_dir = RUNS_ROOT / run_id
    partial = run_dir / "aggregates_partial.json"
    target = partial if partial.exists() else run_dir / "aggregates.json"
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def resolve_run_id(run_id: str) -> str:
    if run_id:
        return run_id
    latest = RUNS_ROOT / "LATEST"
    if latest.exists():
        return latest.read_text(encoding="utf-8").strip()
    return ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_id", default="", help="Run id (default: LATEST)")
    parser.add_argument("--port", type=int, default=8008)
    args = parser.parse_args()

    run_id = resolve_run_id(args.run_id)
    if not run_id:
        print("ERROR: missing run_id and no LATEST pointer")
        return 1

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    server.run_id = run_id
    print(f"Serving http://127.0.0.1:{args.port} (run_id={run_id})")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
