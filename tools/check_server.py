"""Static server for the browser checks that also accepts the results back.

The page cannot write to disk, and scraping the DOM from headless Chrome proved unreliable
while a large asynchronous download was outstanding. Posting the results to the server that
served the page is the simplest arrangement that terminates deterministically.
"""

import http.server
import socketserver
import sys
from pathlib import Path

PORT = int(sys.argv[1])
RESULTS = Path(sys.argv[2])
ROOT = Path(__file__).resolve().parent.parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_POST(self):
        if self.path == "/__results":
            length = int(self.headers.get("Content-Length", 0))
            RESULTS.write_bytes(self.rfile.read(length))
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error(404)

    def log_message(self, *args):
        pass


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    httpd.serve_forever()
