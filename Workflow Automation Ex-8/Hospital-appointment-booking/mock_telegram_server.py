import http.server
import socketserver
import json

PORT = 9090

class TelegramMockHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(length)
        body_str = body_bytes.decode('utf-8')
        
        print(f"[Mock Telegram] Received notification request at {self.path}")
        try:
            payload = json.loads(body_str)
            print(f"   -> Recipient: {payload.get('chat_id')}")
            print(f"   -> Message:   {payload.get('text')}")
        except Exception:
            print(f"   -> Raw Body: {body_str}")

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {
            "ok": True,
            "result": {
                "message_id": 1001,
                "status": "delivered",
                "chat_id": payload.get('chat_id') if 'payload' in locals() else "unknown"
            }
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format, *args):
        # Suppress default server log
        return

def run_mock_server():
    print(f"==================================================")
    print(f" Mock Telegram Server running on http://localhost:{PORT}")
    print(f" Endpoints: POST /bot{{secrets.TELEGRAM_BOT_TOKEN}}/sendMessage")
    print(f"==================================================")
    with socketserver.TCPServer(("", PORT), TelegramMockHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    run_mock_server()
