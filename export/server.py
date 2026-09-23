import http.server
import os

TRANSPARENT_PNG = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

class CacheHandler(http.server.SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1" # Enables Keep-Alive

    def do_GET(self):
        path_clean = self.path.split('?')[0]
        # Pokud je požadována dlaždice, která na disku neexistuje (např. mimo rozměr mapy),
        # vrátíme okamžitě 1x1 transparentní PNG, aby prohlížeč nehlásil 404 a nevznikaly bílé/šedé díry
        if '/tiles/' in path_clean:
            local_path = self.translate_path(self.path)
            if not os.path.exists(local_path):
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(TRANSPARENT_PNG)))
                self.send_header('Cache-Control', 'public, max-age=31536000')
                super().end_headers()
                self.wfile.write(TRANSPARENT_PNG)
                return
        super().do_GET()
    
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
