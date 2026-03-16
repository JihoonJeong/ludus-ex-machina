"""LxM Match Viewer — Python HTTP server with match data API."""

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent.parent))
from lxm.elo import build_leaderboard
from viewer.exporters.tictactoe import TicTacToeFrameRenderer
from viewer.exporters.chess import ChessFrameRenderer


PROJECT_ROOT = Path(__file__).parent.parent
MATCHES_DIR = PROJECT_ROOT / "matches"
STATIC_DIR = Path(__file__).parent / "static"

# Matches without result.json whose log.json hasn't been modified
# in this many seconds are considered dead and auto-cleaned.
STALE_MATCH_TIMEOUT = 300  # 5 minutes


class ViewerHandler(SimpleHTTPRequestHandler):
    """Serves static files and match data API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/matches":
            self._handle_match_list()
        elif path == "/api/leaderboard":
            self._handle_leaderboard()
        elif path.startswith("/api/match/") and path.endswith("/stream"):
            self._handle_sse_stream(path)
        elif path.startswith("/api/match/") and path.endswith("/export"):
            self._handle_export(path, parsed.query)
        elif path.startswith("/api/match/"):
            self._handle_match_data(path)
        else:
            super().do_GET()

    def _handle_match_list(self):
        """List all match folders."""
        matches = []
        if MATCHES_DIR.exists():
            for d in sorted(MATCHES_DIR.iterdir(), reverse=True):
                if not d.is_dir():
                    continue
                config_path = d / "match_config.json"
                if not config_path.exists():
                    continue
                try:
                    config = json.loads(config_path.read_text())
                except (json.JSONDecodeError, OSError):
                    continue

                result_path = d / "result.json"
                result = None
                if result_path.exists():
                    try:
                        result = json.loads(result_path.read_text())
                    except (json.JSONDecodeError, OSError):
                        pass

                log_path = d / "log.json"
                turn_count = 0
                if log_path.exists():
                    try:
                        log = json.loads(log_path.read_text())
                        turn_count = len([e for e in log if e.get("result") == "accepted" or (e.get("result") == "timeout" and e.get("post_move_state"))])
                    except (json.JSONDecodeError, OSError):
                        pass

                # Auto-clean stale matches: no result.json + log.json not
                # modified for STALE_MATCH_TIMEOUT seconds → dead process.
                if not result and log_path.exists():
                    age = time.time() - log_path.stat().st_mtime
                    if age > STALE_MATCH_TIMEOUT:
                        try:
                            shutil.rmtree(d)
                        except OSError:
                            pass
                        continue

                matches.append({
                    "match_id": config.get("match_id", d.name),
                    "game": config.get("game", {}).get("name", "unknown"),
                    "agents": [a.get("display_name", a.get("agent_id")) for a in config.get("agents", [])],
                    "agent_ids": [a.get("agent_id") for a in config.get("agents", [])],
                    "status": "completed" if result else "in_progress",
                    "result": result,
                    "turn_count": turn_count,
                    "timestamp": d.stat().st_mtime,
                })

        self._json_response(matches)

    def _handle_leaderboard(self):
        """Build and return leaderboard from match data."""
        data = build_leaderboard(str(MATCHES_DIR))
        self._json_response(data)

    def _handle_match_data(self, path: str):
        """Handle /api/match/{match_id}/{resource} requests."""
        parts = path.split("/")
        # /api/match/{match_id}/{resource}
        if len(parts) < 5:
            self._error_response(400, "Invalid path")
            return

        match_id = parts[3]
        resource = parts[4]

        match_dir = MATCHES_DIR / match_id
        if not match_dir.exists():
            self._error_response(404, f"Match '{match_id}' not found")
            return

        file_map = {
            "config": "match_config.json",
            "log": "log.json",
            "result": "result.json",
            "state": "state.json",
        }

        filename = file_map.get(resource)
        if not filename:
            self._error_response(404, f"Unknown resource '{resource}'")
            return

        filepath = match_dir / filename
        if not filepath.exists():
            self._error_response(404, f"{filename} not found")
            return

        try:
            data = json.loads(filepath.read_text())
            self._json_response(data)
        except (json.JSONDecodeError, OSError) as e:
            self._error_response(500, str(e))

    def _handle_export(self, path: str, query: str):
        """Generate and serve a GIF or MP4 export of a match."""
        parts = path.split("/")
        match_id = parts[3]
        match_dir = MATCHES_DIR / match_id

        if not match_dir.exists():
            self._error_response(404, f"Match '{match_id}' not found")
            return

        try:
            config = json.loads((match_dir / "match_config.json").read_text())
            log = json.loads((match_dir / "log.json").read_text())
            result_path = match_dir / "result.json"
            result = json.loads(result_path.read_text()) if result_path.exists() else None
        except (json.JSONDecodeError, OSError) as e:
            self._error_response(500, str(e))
            return

        accepted = [e for e in log if e.get("result") == "accepted" or (e.get("result") == "timeout" and e.get("post_move_state"))]
        game_name = config.get("game", {}).get("name")

        renderers = {"tictactoe": TicTacToeFrameRenderer, "chess": ChessFrameRenderer}
        RendererClass = renderers.get(game_name)
        if not RendererClass:
            self._error_response(400, f"No renderer for game: {game_name}")
            return

        params = parse_qs(query)
        speed = float(params.get("speed", ["1"])[0])
        fmt = params.get("format", ["gif"])[0]
        base_duration = int(1500 / speed)
        result_hold = int(3000 / speed)

        renderer = RendererClass()
        agents = config.get("agents", [])
        total = len(accepted)
        state = renderer.initial_state(config)

        frames = [renderer.render_frame(state, 0, total, agents, None)]
        for i, entry in enumerate(accepted):
            state = renderer.apply_move(state, entry)
            frames.append(renderer.render_frame(state, i + 1, total, agents, entry))
        if result:
            frames.append(renderer.render_result_frame(state, result, agents, total))

        if fmt == "mp4":
            self._serve_mp4(frames, match_id, base_duration, result_hold)
        else:
            self._serve_gif(frames, match_id, base_duration, result_hold)

    def _serve_gif(self, frames, match_id, base_duration, result_hold):
        durations = [base_duration * 2]
        for _ in range(len(frames) - 2 if len(frames) > 2 else len(frames) - 1):
            durations.append(base_duration)
        if len(frames) > 1:
            durations.append(result_hold)

        buf = io.BytesIO()
        frames[0].save(
            buf, format="GIF", save_all=True,
            append_images=frames[1:],
            duration=durations, loop=0, optimize=True,
        )
        body = buf.getvalue()

        filename = f"{match_id}.gif"
        self.send_response(200)
        self.send_header("Content-Type", "image/gif")
        self.send_header("Content-Length", len(body))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_mp4(self, frames, match_id, base_duration, result_hold):
        if not shutil.which("ffmpeg"):
            self._error_response(500, "ffmpeg not installed on server")
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            fps = 4
            frame_idx = 0

            def write_copies(img, duration_ms):
                nonlocal frame_idx
                n_copies = max(1, round(duration_ms / 1000 * fps))
                for _ in range(n_copies):
                    img.save(tmpdir / f"frame_{frame_idx:04d}.png")
                    frame_idx += 1

            write_copies(frames[0], base_duration * 2)
            for f in frames[1:-1] if len(frames) > 2 else frames[1:]:
                write_copies(f, base_duration)
            if len(frames) > 1:
                write_copies(frames[-1], result_hold)

            output_path = tmpdir / "output.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(fps),
                "-i", str(tmpdir / "frame_%04d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "23",
                str(output_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                self._error_response(500, f"ffmpeg error: {proc.stderr[:500]}")
                return

            body = output_path.read_bytes()

        filename = f"{match_id}.mp4"
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", len(body))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_sse_stream(self, path: str):
        """SSE endpoint: /api/match/{match_id}/stream — streams new moves in real-time."""
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        parts = path.split("/")
        match_id = parts[3]
        match_dir = MATCHES_DIR / match_id

        if not match_dir.exists():
            self._error_response(404, f"Match '{match_id}' not found")
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Skip moves the client already has
        last_accepted_count = int(params.get("from", ["0"])[0])
        log_path = match_dir / "log.json"
        result_path = match_dir / "result.json"

        try:
            while True:
                # Read current log
                if log_path.exists():
                    try:
                        log = json.loads(log_path.read_text())
                        accepted = [e for e in log if e.get("result") == "accepted" or (e.get("result") == "timeout" and e.get("post_move_state"))]
                    except (json.JSONDecodeError, OSError):
                        accepted = []
                else:
                    accepted = []

                # Send new moves
                if len(accepted) > last_accepted_count:
                    for entry in accepted[last_accepted_count:]:
                        data = json.dumps({"type": "move", "entry": entry})
                        self.wfile.write(f"data: {data}\n\n".encode())
                    self.wfile.flush()
                    last_accepted_count = len(accepted)

                # Check for result
                if result_path.exists():
                    try:
                        result = json.loads(result_path.read_text())
                        data = json.dumps({"type": "result", "result": result})
                        self.wfile.write(f"data: {data}\n\n".encode())
                        self.wfile.flush()
                    except (json.JSONDecodeError, OSError):
                        pass
                    break

                # Detect dead match: log.json not updated for too long
                if log_path.exists():
                    age = time.time() - log_path.stat().st_mtime
                    if age > STALE_MATCH_TIMEOUT:
                        data = json.dumps({
                            "type": "dead",
                            "message": "Match process appears to have died",
                        })
                        self.wfile.write(f"data: {data}\n\n".encode())
                        self.wfile.flush()
                        # Auto-clean
                        try:
                            shutil.rmtree(match_dir)
                        except OSError:
                            pass
                        break

                time.sleep(2)
        except (BrokenPipeError, ConnectionResetError):
            pass  # Client disconnected

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _error_response(self, code: int, message: str):
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Quieter logging — only log API calls."""
        if "/api/" in (args[0] if args else ""):
            super().log_message(format, *args)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser(description="LxM Match Viewer Server")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    server = ThreadingHTTPServer(("0.0.0.0", args.port), ViewerHandler)
    print(f"LxM Viewer running at http://localhost:{args.port}")
    print(f"Serving matches from: {MATCHES_DIR}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
