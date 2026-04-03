"""Native Toga launcher for F4U.

Provides a native macOS/Linux window that:
1. Starts the FastAPI server in a background thread
2. Shows a button to open the web browser
3. Displays server status
"""

import threading
import webbrowser
import toga
from toga.style import Pack
from toga.style.pack import COLUMN, CENTER

# Server configuration
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


class F4UApp(toga.App):
    def startup(self):
        self.server_running = False

        # Main window
        self.main_window = toga.MainWindow(title=self.formal_name, size=(400, 300))

        # Status label
        self.status_label = toga.Label(
            "Starting server...",
            style=Pack(padding=(20, 10), text_align=CENTER)
        )

        # Open Dashboard button
        self.open_btn = toga.Button(
            "Open Dashboard",
            on_press=self.open_dashboard,
            enabled=False,
            style=Pack(padding=10, width=200)
        )

        # URL display
        url_label = toga.Label(
            URL,
            style=Pack(padding=(20, 10), text_align=CENTER, color="#888888")
        )

        # Layout
        box = toga.Box(
            children=[
                toga.Label(
                    "F4U",
                    style=Pack(padding=(30, 10), text_align=CENTER, font_size=24, font_weight="bold")
                ),
                toga.Label(
                    "Finance For You",
                    style=Pack(padding=(0, 10), text_align=CENTER)
                ),
                self.status_label,
                self.open_btn,
                url_label,
            ],
            style=Pack(direction=COLUMN, alignment=CENTER, padding=20)
        )

        self.main_window.content = box
        self.main_window.show()

        # Start server in background
        self._start_server()

    def _start_server(self):
        """Start the FastAPI server in a background thread."""
        def run():
            import uvicorn
            from f4u.server import app
            uvicorn.run(
                app,
                host=HOST,
                port=PORT,
                log_level="warning"
            )

        server_thread = threading.Thread(target=run, daemon=True)
        server_thread.start()

        # Check server status after delay
        self.loop.call_later(1.0, self._check_server)

    def _check_server(self):
        """Check if server is running and update UI."""
        import urllib.request
        import urllib.error

        try:
            urllib.request.urlopen(f"{URL}/api/health", timeout=1)
            self.server_running = True
            self.status_label.text = "Server running"
            self.open_btn.enabled = True
            # Auto-open browser
            webbrowser.open(URL)
        except (urllib.error.URLError, Exception):
            # Retry
            self.loop.call_later(0.5, self._check_server)

    def open_dashboard(self, widget):
        """Open the dashboard in default browser."""
        webbrowser.open(URL)


def main():
    """Entry point for the application."""
    return F4UApp(
        formal_name="Finance For You",
        app_id="com.hartmann.f4u",
        app_name="f4u"
    )


if __name__ == "__main__":
    main().main_loop()
