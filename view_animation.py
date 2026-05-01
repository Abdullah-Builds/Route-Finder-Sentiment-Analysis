import http.server
import socketserver
import webbrowser
import os
import threading
import time
import sys
from dotenv import load_dotenv
load_dotenv()

PORT = int(os.getenv("PORT", 8000)) 
FILE = "astar_visualizer.html"

def start_server():
    Handler = http.server.SimpleHTTPRequestHandler
    # Allow address reuse to avoid "Address already in use" errors on restart
    socketserver.TCPServer.allow_reuse_address = True
    try:
        with socketserver.TCPServer(("", PORT), Handler) as httpd:
            print(f"\n🚀 Server started at http://localhost:{PORT}")
            httpd.serve_forever()
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if not os.path.exists(FILE):
        print(f"❌ Error: {FILE} not found in the current directory.")
        sys.exit(1)

    # Start server in a background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Wait a moment for the server to initialize
    time.sleep(1)

    # Open the visualizer in the browser
    url = f"http://localhost:{PORT}/{FILE}"
    print(f"🌐 Opening {FILE} in your browser...")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"⚠️ Could not open browser automatically: {e}")
        print(f"Please open this URL manually: {url}")

    print("\n💡 Tip: Press Ctrl+C to stop the server when you are done.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping server...")
        sys.exit(0)
