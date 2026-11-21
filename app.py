"""Мир Слоновых: локальный видеопортал на стандартной библиотеке Python."""
import json
import mimetypes
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config.json"
EXTS = {".mp4", ".m4v", ".webm", ".ogv", ".mov", ".mkv", ".avi"}
PORT = int(os.environ.get("SLONOV_PORT", "8000"))


def media_root():
    try:
        path = Path(json.loads(CONFIG.read_text(encoding="utf-8"))["media_folder"]).expanduser().resolve()
        return path if path.is_dir() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def library():
    root = media_root()
    if root is None:
        return []
    result = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(names):
            path = Path(folder) / name
            if path.suffix.lower() in EXTS:
                result.append({"id": path.relative_to(root).as_posix(),
                               "title": path.stem.replace("_", " "),
                               "category": path.parent.name if path.parent != root else "Мультфильмы"})
    return result


class Handler(BaseHTTPRequestHandler):
    def respond(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urllib.parse.urlsplit(self.path).path
        if route == "/":
            return self.respond((ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        if route == "/api/library":
            return self.respond(json.dumps({"items": library(), "configured": media_root() is not None},
                                           ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
        if route.startswith("/video/"):
            root = media_root()
            if root is None:
                return self.send_error(404)
            path = (root / urllib.parse.unquote(route[7:])).resolve()
            if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in EXTS:
                return self.send_error(404)
            return self.video(path)
        self.send_error(404)

    def video(self, path):
        size = path.stat().st_size
        start, end = 0, size - 1
        header = self.headers.get("Range")
        if header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
            if not match or (not match[1] and not match[2]):
                return self.send_error(416)
            if not match[1]:
                start = max(0, size - int(match[2]))
            else:
                start = int(match[1])
                if match[2]:
                    end = min(end, int(match[2]))
            if start >= size or end < start:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
        self.send_response(206 if header else 200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with path.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = stream.read(min(262144, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    print(f"Мир Слоновых: http://localhost:{PORT}")
    if media_root() is None:
        print("Укажите путь к мультфильмам в config.json.")
    try:
        ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
