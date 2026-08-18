import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
import re
import socket
import threading
import time
from typing import Any

from app.telegram.adapter import TDLibAdapter

logger = logging.getLogger("tmusic.network.stream")


class TDLibStreamHandler(BaseHTTPRequestHandler):
    """Precision HTTP Handler supporting Range requests and exact chunk boundaries."""

    adapter: TDLibAdapter | None = None
    server_ref: Any = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress standard HTTP server console noise."""
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

        # 2. Parse HTTP Range header if requested by player for seeking
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

        if not first_chunk:
            self.send_error(504, "Stream buffer timeout")
            return

        # 4. Send HTTP Headers (206 if Range requested, 200 otherwise)
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

        # Write first chunk
        try:
            self.wfile.write(first_chunk)
            self.wfile.flush()
        except Exception:
            return

        offset += len(first_chunk)

        # 5. Continuous Progressive Streaming Loop with Exact Boundary Capping
        empty_retries = 0
        while empty_retries < 150:
            if file_size > 0 and offset >= file_size:
                break  # Stream reached exact 100% end of file!

            if end_offset and offset > end_offset:
                break

            # Cap requested count to remaining bytes so TDLib never rejects the final chunk
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
                break  # Player paused, seeked, or switched track
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

    def get_file_size(self, file_id: int) -> int:
        return self._file_sizes.get(file_id, 0)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()