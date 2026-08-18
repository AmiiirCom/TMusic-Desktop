import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
from pathlib import Path
import re
import socket
import threading
import time
from typing import Any

from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.network.stream")


class TDLibStreamHandler(BaseHTTPRequestHandler):
    """Precision HTTP Handler supporting live TDLib stream and fast local disk fallback."""

    adapter: TDLibAdapter | None = None
    server_ref: Any = None

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_GET(self) -> None:
        match = re.match(r"^/stream/(\d+)$", self.path)
        if not match or not self.adapter:
            self.send_error(404, "Invalid stream URL")
            return

        file_id = int(match.group(1))
        file_size = self.server_ref.get_file_size(file_id) if self.server_ref else 0

        # 1. Trigger TDLib download with maximum priority 32
        self.adapter.send({
            "@type": "downloadFile",
            "file_id": file_id,
            "priority": 32,
            "offset": 0,
            "limit": 0,
            "synchronous": False,
        })

        # 2. Parse Range header if present
        range_header = self.headers.get("Range")
        start_offset = 0
        end_offset = file_size - 1 if file_size > 0 else None

        if range_header and file_size > 0:
            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match:
                start_offset = int(range_match.group(1))
                if range_match.group(2):
                    end_offset = int(range_match.group(2))

        chunk_size = 64 * 1024
        offset = start_offset

        # 3. Wait for initial chunk at offset
        initial_count = min(chunk_size, (end_offset - offset + 1)) if end_offset else chunk_size
        first_chunk: bytes | None = None
        retries = 0

        while retries < 60:
            # Check if file has already finished downloading to disk
            completed_file = self.server_ref.get_completed_path(file_id) if self.server_ref else None
            if completed_file and Path(completed_file).exists() and Path(completed_file).stat().st_size > offset:
                break

            res = self.adapter.request_sync({
                "@type": "readFilePart",
                "file_id": file_id,
                "offset": offset,
                "count": initial_count,
            }, timeout=0.6)

            if res and res.get("@type") == "data":
                data_b64 = res.get("data", "")
                if data_b64:
                    try:
                        first_chunk = base64.b64decode(data_b64)
                        if first_chunk:
                            break
                    except Exception:
                        pass
            time.sleep(0.08)
            retries += 1

        # 4. Send HTTP 200/206 Response Headers
        if range_header and file_size > 0 and end_offset is not None:
            content_len = end_offset - start_offset + 1
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start_offset}-{end_offset}/{file_size}")
        else:
            content_len = file_size if file_size > 0 else None
            self.send_response(200)

        self.send_header("Content-Type", "audio/mpeg")
        if content_len is not None:
            self.send_header("Content-Length", str(content_len))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Connection", "close")
        self.end_headers()

        # Write first chunk if obtained via readFilePart
        if first_chunk:
            try:
                self.wfile.write(first_chunk)
                self.wfile.flush()
                offset += len(first_chunk)
            except Exception:
                return

        # 5. Streaming Loop (Switches to fast disk reading as soon as file completes)
        empty_retries = 0
        while empty_retries < 150:
            if file_size > 0 and offset >= file_size:
                break

            if end_offset and offset > end_offset:
                break

            # Fast Path: If download finished to disk, stream remaining bytes directly from disk file!
            completed_file = self.server_ref.get_completed_path(file_id) if self.server_ref else None
            if completed_file and Path(completed_file).exists() and Path(completed_file).stat().st_size > offset:
                try:
                    with open(completed_file, "rb") as f:
                        f.seek(offset)
                        while True:
                            rem = (file_size - offset) if file_size > 0 else chunk_size
                            if rem <= 0:
                                break
                            buf = f.read(min(chunk_size, rem))
                            if not buf:
                                break
                            self.wfile.write(buf)
                            self.wfile.flush()
                            offset += len(buf)
                    break
                except Exception:
                    break

            # Progressive TDLib readFilePart Loop
            if file_size > 0:
                remaining = file_size - offset
                if remaining <= 0:
                    break
                requested_count = min(chunk_size, remaining)
            else:
                requested_count = chunk_size

            try:
                res = self.adapter.request_sync({
                    "@type": "readFilePart",
                    "file_id": file_id,
                    "offset": offset,
                    "count": requested_count,
                }, timeout=0.6)

                if res and res.get("@type") == "data":
                    data_b64 = res.get("data", "")
                    if data_b64:
                        chunk = base64.b64decode(data_b64)
                        if chunk:
                            self.wfile.write(chunk)
                            self.wfile.flush()
                            offset += len(chunk)
                            empty_retries = 0
                            continue

                time.sleep(0.15)
                empty_retries += 1

            except (BrokenPipeError, ConnectionResetError):
                break
            except Exception:
                break


class LocalStreamServer:
    """Zero-dependency localhost streaming proxy server."""

    def __init__(self, adapter: TDLibAdapter) -> None:
        self._adapter = adapter
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port = 0
        self._file_sizes: dict[int, int] = {}
        self._completed_paths: dict[int, str] = {}
        self._start_server()

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _start_server(self) -> None:
        self._port = self._find_free_port()
        TDLibStreamHandler.adapter = self._adapter
        TDLibStreamHandler.server_ref = self

        self._server = ThreadingHTTPServer(("127.0.0.1", self._port), TDLibStreamHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("Local Audio Streaming Server running on http://127.0.0.1:%d", self._port)

    def get_stream_url(self, file_id: int, size_bytes: int = 0) -> str:
        if size_bytes > 0:
            self._file_sizes[file_id] = size_bytes
        return f"http://127.0.0.1:{self._port}/stream/{file_id}"

    def register_completed_file(self, file_id: int, local_path: str) -> None:
        """Register completed file path for instant local disk serving."""
        self._completed_paths[file_id] = local_path

    def get_completed_path(self, file_id: int) -> str | None:
        return self._completed_paths.get(file_id)

    def get_file_size(self, file_id: int) -> int:
        return self._file_sizes.get(file_id, 0)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()