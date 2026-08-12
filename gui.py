"""
BindCraft Desktop GUI Entry Point
Wraps the FastAPI application in a native desktop window using pywebview.
"""
import sys
import threading
import time
import webview
import uvicorn
import socket

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_server():
    """Start the FastAPI backend."""
    # Run uvicorn programmatically
    # log_config=None keeps standard logging from main.py
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, log_level="info")

if __name__ == '__main__':
    # 1. Check if the port is already in use (maybe a server is already running?)
    # If not, start the server in a background daemon thread
    if not is_port_in_use(8000):
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        # Wait a moment for the server to boot up
        for _ in range(30):
            if is_port_in_use(8000):
                break
            time.sleep(0.1)

    # 2. Create the native desktop window
    # We load the local server URL. The webview acts as our frontend.
    window = webview.create_window(
        title='BindCraft \U0001f52c', # Microscope emoji
        url='http://127.0.0.1:8000',
        width=1200,
        height=800,
        min_size=(900, 600),
        background_color='#0f172a' # Match our dark mode background
    )

    # 3. Start the GUI event loop
    # On Windows, this uses Edge Chromium (WebView2) by default
    webview.start(private_mode=False)
