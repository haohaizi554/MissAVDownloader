import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin, urlparse

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None


def is_curl_cffi_available():
    return cffi_requests is not None


def should_use_local_hls_proxy(m3u8_url):
    host = urlparse(m3u8_url).netloc.lower()
    if "surrit" in host:
        return True
    if m3u8_url.lower().endswith(".m3u8") or "playlist.m3u8" in m3u8_url.lower():
        return True
    return False


class HlsLocalProxy:
    """Local HLS proxy: curl_cffi upstream + rewritten playlist for N_m3u8DL-RE."""

    def __init__(self, referer, user_agent, cookies=None, external_proxy=None, host="127.0.0.1"):
        self.referer = referer
        self.user_agent = user_agent
        self.cookies = dict(cookies or {})
        self.external_proxy = external_proxy
        self.host = host
        self.trace_id = uuid.uuid4().hex[:8]
        self._url_to_id = {}
        self._id_to_url = {}
        self._next_id = 0
        self._playlist_cache = {}
        self._lock = threading.Lock()
        self.bytes_served = 0
        self.segments_served = 0
        self._server = None
        self._thread = None
        self.port = 0
        self.base_url = ""

    def _origin_from_referer(self):
        parsed = urlparse(self.referer)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
        return self.referer

    def _upstream_proxies(self):
        if not self.external_proxy:
            return None
        return {"http": self.external_proxy, "https": self.external_proxy}

    def _fetch_upstream(self, url):
        if cffi_requests is None:
            raise RuntimeError("curl_cffi is not installed")
        headers = {
            "Referer": self.referer,
            "Origin": self._origin_from_referer(),
            "User-Agent": self.user_agent,
        }
        response = cffi_requests.get(
            url,
            impersonate="chrome",
            headers=headers,
            cookies=self.cookies,
            proxies=self._upstream_proxies(),
            timeout=60,
            allow_redirects=True,
        )
        return response

    @staticmethod
    def _is_valid_playlist(status_code, body):
        if status_code not in (200, 206):
            return False
        if not body:
            return False
        try:
            text = body.decode("utf-8", errors="ignore")
        except Exception:
            return False
        return "#EXTM3U" in text

    @staticmethod
    def _looks_like_playlist_url(url):
        lower = url.lower()
        return lower.endswith(".m3u8") or "playlist.m3u8" in lower or ".m3u8?" in lower

    def wrap(self, upstream_url):
        with self._lock:
            if upstream_url in self._url_to_id:
                rid = self._url_to_id[upstream_url]
            else:
                self._next_id += 1
                rid = self._next_id
                self._url_to_id[upstream_url] = rid
                self._id_to_url[rid] = upstream_url
        return f"{self.base_url}/r/{rid}"

    def rewrite_playlist(self, text, playlist_url):
        output = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                output.append("")
                continue
            if line.startswith("#"):
                def repl(match):
                    uri = match.group(1)
                    absolute = urljoin(playlist_url, uri)
                    return f'URI="{self.wrap(absolute)}"'

                output.append(re.sub(r'URI="([^"]+)"', repl, line))
            else:
                absolute = urljoin(playlist_url, line)
                output.append(self.wrap(absolute))
        return "\n".join(output) + ("\n" if text.endswith("\n") else "")

    def fetch_resource(self, upstream_url):
        is_playlist_req = self._looks_like_playlist_url(upstream_url)
        if is_playlist_req:
            with self._lock:
                cached = self._playlist_cache.get(upstream_url)
            if cached is not None:
                body, content_type = cached
                with self._lock:
                    self.bytes_served += len(body)
                return body, content_type

        response = self._fetch_upstream(upstream_url)
        body = response.content or b""
        content_type = response.headers.get("Content-Type", "application/octet-stream")

        if self._is_valid_playlist(response.status_code, body):
            text = body.decode("utf-8", errors="ignore")
            rewritten = self.rewrite_playlist(text, upstream_url).encode("utf-8")
            with self._lock:
                self._playlist_cache[upstream_url] = (rewritten, "application/vnd.apple.mpegurl")
                self.bytes_served += len(rewritten)
            return rewritten, "application/vnd.apple.mpegurl"

        if response.status_code not in (200, 206):
            raise RuntimeError(f"upstream HTTP {response.status_code} for {upstream_url[:120]}")

        with self._lock:
            self.bytes_served += len(body)
            if not is_playlist_req:
                self.segments_served += 1
        return body, content_type

    def get_stats(self):
        with self._lock:
            return {
                "bytes_served": self.bytes_served,
                "segments_served": self.segments_served,
                "trace_id": self.trace_id,
            }

    def start(self):
        if self._server is not None:
            return self.base_url

        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                return

            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/stats":
                    stats = proxy.get_stats()
                    payload = (
                        f'{{"bytes_served":{stats["bytes_served"]},'
                        f'"segments_served":{stats["segments_served"]},'
                        f'"trace_id":"{stats["trace_id"]}"}}'
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                if not path.startswith("/r/"):
                    self.send_error(404)
                    return
                try:
                    rid = int(path[3:].strip("/"))
                except ValueError:
                    self.send_error(400)
                    return

                upstream = proxy._id_to_url.get(rid)
                if not upstream:
                    self.send_error(404)
                    return

                try:
                    body, content_type = proxy.fetch_resource(upstream)
                except Exception as exc:
                    self.send_error(502, explain=str(exc))
                    return

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer((self.host, 0), Handler)
        self.port = self._server.server_address[1]
        self.base_url = f"http://{self.host}:{self.port}"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.base_url

    def stop(self):
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=3)
        self._server = None
        self._thread = None
