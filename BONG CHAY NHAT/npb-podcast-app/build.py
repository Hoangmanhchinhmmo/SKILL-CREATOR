"""
PyInstaller build script — Package NPB Podcast Writer as .exe
Usage: python build.py
"""

import PyInstaller.__main__
import os

APP_NAME = "NPB-Podcast-Writer"
MAIN_SCRIPT = "main.py"
ICON_PATH = os.path.join("assets", "icon.ico")

# Paths to include
SKILL_DIR = os.path.abspath(os.path.join("..", "Skill-bong-chay"))

args = [
    MAIN_SCRIPT,
    "--name", APP_NAME,
    "--onefile",
    "--windowed",
    "--noconfirm",
    "--clean",
    # Add skill-bong-chay as data
    "--add-data", f"{SKILL_DIR};Skill-bong-chay",
    # Hidden imports for Flet
    "--hidden-import", "flet",
    "--hidden-import", "flet_core",
    "--hidden-import", "flet_runtime",
    "--hidden-import", "cryptography",
    "--hidden-import", "requests",
    # Exclude unnecessary modules to reduce size
    "--exclude-module", "matplotlib",
    "--exclude-module", "numpy",
    "--exclude-module", "pandas",
    "--exclude-module", "PIL",
    "--exclude-module", "tkinter",
]

# Add icon if exists
if os.path.exists(ICON_PATH):
    args.extend(["--icon", ICON_PATH])

if __name__ == "__main__":
    print(f"Building {APP_NAME}...")
    PyInstaller.__main__.run(args)
    print(f"\nDone! Output: dist/{APP_NAME}.exe")
