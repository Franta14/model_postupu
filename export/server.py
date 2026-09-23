import http.server

class CacheHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1" # Enables Keep-Alive
    
    def end_headers(self):
        # Cache tiles and thumbs images, but no-cache for HTML, JS, CSS, JSON metadata and service worker
        path_clean = self.path.split('?')[0]
        if path_clean.endswith(('.html', '.js', '.css', '.json')) or path_clean.endswith('/') or 'sw.js' in path_clean:
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        else:
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
