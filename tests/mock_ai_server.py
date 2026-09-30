# A stand-in AI server for tests: speaks Anthropic's streaming Messages API
# and the OpenAI-compatible chat API, with no real model behind it.
#   python3 tests/mock_ai_server.py 8765     (serve until stopped)

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SEEN = {}


def sse(events):
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_GET(self):
        if self.path.endswith("/models"):
            self._send(200, {"data": [{"id": "tiny-model"}, {"id": "big-model"}]})
        else:
            self._send(404, {"error": {"message": "nope"}})

    def do_POST(self):
        body = self._body()
        SEEN["path"], SEEN["body"], SEEN["headers"] = self.path, body, dict(self.headers)
        if self.path.startswith("/v1/messages"):
            if self.headers.get("x-api-key") == "bad-key":
                return self._send(401, {"type": "error", "error": {
                    "type": "authentication_error", "message": "invalid x-api-key"}})
            text = ["Hello ", "from ", "Claude!"]
            events = [("message_start", {"type": "message_start", "message": {
                "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                "content": [], "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 0}}}),
                ("content_block_start", {"type": "content_block_start", "index": 0,
                                         "content_block": {"type": "text", "text": ""}})]
            events += [("content_block_delta", {"type": "content_block_delta", "index": 0,
                                                "delta": {"type": "text_delta", "text": t}})
                       for t in text]
            events += [("content_block_stop", {"type": "content_block_stop", "index": 0}),
                       ("message_delta", {"type": "message_delta",
                                          "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                                          "usage": {"output_tokens": 5}}),
                       ("message_stop", {"type": "message_stop"})]
            payload = sse(events).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.endswith("/chat/completions"):
            if self.headers.get("Authorization") == "Bearer bad-key":
                return self._send(401, {"error": {"message": "Invalid key"}})
            chunks = ["Hi ", "from ", "OpenAI-style!"]
            payload = "".join(f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}\n\n"
                              for c in chunks) + "data: [DONE]\n\n"
            data = payload.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._send(404, {"error": {"message": "unknown"}})

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)




def serve(port=0):
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    server = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
    print(f"mock AI on port {server.server_port}", flush=True)
    server.serve_forever()
