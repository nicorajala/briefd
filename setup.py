from pathlib import Path
import sys
import os
import shutil
import subprocess
from pathlib import Path

def get_app_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home()
    app_dir = base / "briefd"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir

def install_packages():
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def create_launcher():
    script_dir = Path(__file__).parent.resolve()
    main_script = script_dir / "briefd.py"

    if sys.platform == "win32":
        # create a .bat file in the script dir and add it to PATH via user env
        launcher = script_dir / "briefd.bat"
        launcher.write_text(f'@echo off\npython "{main_script}" %*\n')

        # add to user PATH
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            "Environment",
            0, winreg.KEY_READ | winreg.KEY_WRITE
        )
        current_path, _ = winreg.QueryValueEx(key, "Path")
        if str(script_dir) not in current_path:
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, f"{current_path};{script_dir}")
            winreg.CloseKey(key)
            print(f"Added {script_dir} to PATH — restart your terminal for it to take effect.")
        else:
            print("Already in PATH.")

    else:
        # unix — create a shell script in /usr/local/bin or ~/.local/bin
        local_bin = Path.home() / ".local" / "bin"
        local_bin.mkdir(parents=True, exist_ok=True)
        launcher = local_bin / "briefd"
        launcher.write_text(f'#!/bin/sh\nexec python3 "{main_script}" "$@"\n')
        launcher.chmod(0o755)
        print(f"Launcher created at {launcher}")
        print("Make sure ~/.local/bin is in your PATH.")

def create_default_config():
    config_path = get_app_dir() / "config.toml"
    if config_path.exists():
        print(f"Config already exists at {config_path}, skipping.")
        return
    config_path.write_text("""\
    [user]
    name = "User"
    interests = ["programming", "linux", "technology"]

    [[sources]]
    name = "Hacker News"
    url = "https://news.ycombinator.com/rss"
    category = "tech"
    enabled = true

    [[sources]]
    name = "BBC News"
    url = "https://feeds.bbci.co.uk/news/rss.xml"
    category = "world"
    enabled = true
    """)
    print(f"Created default config at {config_path}")
    print("Edit it to add your sources and interests.")

if __name__ == "__main__":
    print("=== briefd setup ===\n")
    install_packages()
    create_default_config()
    create_launcher()
    print("\nDone! Run 'briefd' to start.")