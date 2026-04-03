"""Simple FastAPI web server for F4U."""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="F4U - Finance For You")


@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>F4U - Finance For You</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .container {
                text-align: center;
                padding: 2rem;
                background: rgba(255,255,255,0.1);
                border-radius: 16px;
                backdrop-filter: blur(10px);
            }
            h1 { font-size: 3rem; margin-bottom: 0.5rem; }
            p { font-size: 1.2rem; opacity: 0.9; }
            .status {
                margin-top: 2rem;
                padding: 1rem;
                background: rgba(0,255,0,0.2);
                border-radius: 8px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>F4U</h1>
            <p>Finance For You</p>
            <div class="status">
                Server is running
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the uvicorn server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
