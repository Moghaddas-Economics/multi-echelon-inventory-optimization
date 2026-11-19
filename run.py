"""
MultiEchelonDSS — One-Click Streamlit Dashboard Launcher
Execute with: python run.py
"""

import sys
import os
import subprocess
import socket
import webbrowser
import time
import threading


def get_free_port(default_port=8525):
    """Find available port avoiding collision with other active Streamlit instances."""
    for port in range(default_port, default_port + 20):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return default_port


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    app_file = os.path.join(root_dir, "app.py")
    port = get_free_port(8525)

    print("=" * 65)
    print("  MultiEchelonDSS Decision Support System")
    print(f"  Target File : {app_file}")
    print(f"  Port        : {port} (Dedicated DSS Port)")
    print(f"  URL         : http://localhost:{port}")
    print("  Press Ctrl+C to terminate.")
    print("=" * 65)

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_file,
        "--server.port",
        str(port),
    ] + sys.argv[1:]

    try:
        # Auto-open correct dedicated port in default browser
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(f"http://localhost:{port}")), daemon=True).start()
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n[DSS] Dashboard stopped.")


if __name__ == "__main__":
    main()
