import http.server

class CacheHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1" # Enables Keep-Alive
    
    def end_headers(self):
        # Force aggressive caching for 1 year
        self.send_header('Cache-Control', 'public, max-age=31536000')
        super().end_headers()

if __name__ == '__main__':
    print("Spoustim lokalni server na portu 8000 (vicevlaknovy, HTTP/1.1, zapnuta Cache)...")
    http.server.test(
        HandlerClass=CacheHandler,
        ServerClass=http.server.ThreadingHTTPServer,
        port=8000,
        bind='0.0.0.0'
    )
