"""
Build Script — NPB Podcast Writer

Strategy: Build inside a CLEAN virtual environment with ONLY needed packages.
This is an ALLOWLIST approach (not denylist) — no bloated torch/scipy/etc.

Usage:
    python build.py              # Full build: create venv → install → flet pack
    python build.py pack         # Same as above
    python build.py quick        # Skip venv creation if .buildenv/ already exists
    python build.py native       # flet build windows (needs Flutter SDK)
    python build.py clean        # Remove all build artifacts + venv

Output:
  dist/NPB-Podcast-Writer/
    NPB-Podcast-Writer.exe
    Skill-bong-chay/
    _internal/   (runtime)
  dist/NPB-Podcast-Writer.zip   (ready to ship)
"""

import subprocess
import sys
import os
import shutil
import time
import zipfile

# Fix Windows console encoding for Unicode characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ─── Config ───────────────────────────────────────────────────
APP_NAME = "NPB-Podcast-Writer"
MAIN_SCRIPT = "main.py"
ICON_PATH = os.path.join("assets", "icon.ico")
OUTPUT_DIR = "dist"
BUILD_VENV = ".buildenv"  # Dedicated clean venv for building

COMPANY_NAME = "4MMO"
PRODUCT_NAME = "NPB Podcast Writer"
FILE_VERSION = "1.0.0.0"
PRODUCT_VERSION = "1.0.0.0"
FILE_DESCRIPTION = "NPB Podcast Script Generator"
COPYRIGHT = "Copyright 2026 4MMO. All rights reserved."

SKILL_DIR = os.path.abspath(os.path.join("..", "Skill-bong-chay"))
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Files/dirs to exclude when copying Skill-bong-chay
SKILL_EXCLUDE = ("__pycache__", "*.pyc", "output", ".env", ".git", "*.egg-info")

# ─── ALLOWLIST: Only these packages go into the build venv ────
# This is the ONLY list that matters. If it's not here, it's not bundled.
BUILD_REQUIREMENTS = [
    "flet==0.82.2",
    "flet-desktop==0.82.2",
    "cryptography>=42.0.0",
    "requests>=2.31.0",
    "google-generativeai>=0.8.0",
    "python-dotenv>=1.0.0",
    "pyinstaller>=6.0.0",
]


# ─── Helpers ──────────────────────────────────────────────────

def _run(cmd: list[str], label: str = "", env: dict = None) -> None:
    """Run a subprocess command, exit on failure."""
    if label:
        print(f"  -> {label}")
    result = subprocess.run(cmd, cwd=APP_DIR, env=env)
    if result.returncode != 0:
        print(f"\n  FAILED: {' '.join(cmd[:5])}...")
        sys.exit(1)


def _run_in_venv(cmd: list[str], label: str = "") -> None:
    """Run a command using the build venv's Python."""
    venv_python = _get_venv_python()
    _run([venv_python] + cmd, label=label)


def _get_venv_python() -> str:
    """Get path to the build venv's python.exe."""
    venv_dir = os.path.join(APP_DIR, BUILD_VENV)
    if sys.platform == "win32":
        return os.path.join(venv_dir, "Scripts", "python.exe")
    return os.path.join(venv_dir, "bin", "python")


def _folder_size(path: str) -> int:
    """Calculate total folder size in bytes."""
    return sum(
        os.path.getsize(os.path.join(r, f))
        for r, _, files in os.walk(path)
        for f in files
    )


def _copy_skills(dest_dir: str) -> None:
    """Copy Skill-bong-chay pipeline scripts into dest_dir."""
    if not os.path.isdir(SKILL_DIR):
        print(f"  WARNING: Skill dir not found: {SKILL_DIR}")
        print("    Pipeline scripts will NOT be included!")
        return

    dst = os.path.join(dest_dir, "Skill-bong-chay")
    if os.path.exists(dst):
        shutil.rmtree(dst)

    shutil.copytree(SKILL_DIR, dst, ignore=shutil.ignore_patterns(*SKILL_EXCLUDE))
    print(f"  OK Copied Skill-bong-chay -> {dst}")


def _make_zip(folder_path: str) -> str:
    """Create a zip file from a folder for distribution."""
    zip_path = f"{folder_path}.zip"
    if os.path.exists(zip_path):
        os.remove(zip_path)

    print(f"  -> Creating zip: {os.path.basename(zip_path)}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(folder_path))
                zf.write(file_path, arcname)

    zip_size = os.path.getsize(zip_path) / 1024 / 1024
    print(f"  OK Zip created: {zip_size:.0f} MB")
    return zip_path


def _print_banner(mode: str) -> None:
    print()
    print("=" * 60)
    print(f"  Building {APP_NAME}")
    print(f"  Mode: {mode}")
    print(f"  Strategy: Clean venv (allowlist)")
    print("=" * 60)
    print()


def _print_success(output_path: str, mode: str) -> None:
    if os.path.isdir(output_path):
        total = _folder_size(output_path)
        size_str = f"{total / 1024 / 1024:.0f} MB (folder)"
    elif os.path.isfile(output_path):
        total = os.path.getsize(output_path)
        size_str = f"{total / 1024 / 1024:.0f} MB (single file)"
    else:
        print(f"\n  Output not found: {output_path}")
        return

    print()
    print("=" * 60)
    print("  BUILD SUCCESS!")
    print(f"  Output: {os.path.abspath(output_path)}")
    print(f"  Size:   {size_str}")
    print(f"  Mode:   {mode}")
    print()
    print("  Ship: zip entire folder -> user extracts -> runs .exe")
    print("=" * 60)
    print()


# ─── Step 1: Create clean build venv ─────────────────────────

def create_build_venv(force: bool = False) -> None:
    """Create a dedicated virtual environment with ONLY build dependencies.

    This is the key insight: instead of excluding 88 packages from a bloated
    global env (denylist), we create a clean venv with only what we need (allowlist).

    Result: build output is ~100-150 MB instead of 2-5 GB.
    """
    venv_dir = os.path.join(APP_DIR, BUILD_VENV)
    venv_python = _get_venv_python()

    if os.path.exists(venv_python) and not force:
        print(f"  OK Build venv already exists: {BUILD_VENV}/")
        print("     Use 'python build.py clean' then rebuild to recreate.")
        return

    print("[1/4] Creating clean build virtual environment...")
    print(f"  -> {BUILD_VENV}/")

    # Remove old venv if forcing
    if os.path.exists(venv_dir):
        shutil.rmtree(venv_dir)

    # Create new venv
    _run([sys.executable, "-m", "venv", venv_dir], "Creating venv...")

    # Upgrade pip
    _run([venv_python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
         "Upgrading pip...")

    # Install ONLY the packages we need (ALLOWLIST)
    print("  -> Installing build dependencies (allowlist):")
    for pkg in BUILD_REQUIREMENTS:
        print(f"     {pkg}")

    _run(
        [venv_python, "-m", "pip", "install", "--quiet"] + BUILD_REQUIREMENTS,
        "Installing packages...",
    )

    # Verify installation
    result = subprocess.run(
        [venv_python, "-m", "pip", "list", "--format=columns"],
        capture_output=True, text=True, cwd=APP_DIR,
    )
    pkg_count = len(result.stdout.strip().split("\n")) - 2  # minus header
    print(f"  OK Venv ready: {pkg_count} packages (clean!)")

    # Show what's installed for verification
    print()
    print("  Installed packages:")
    for line in result.stdout.strip().split("\n")[2:]:  # skip header
        name = line.split()[0] if line.strip() else ""
        if name:
            print(f"     {line.strip()}")


# ─── Step 2: Build with flet pack inside venv ────────────────

def build_pack(skip_venv: bool = False) -> None:
    """Build using flet pack inside the clean build venv.

    Flow:
    1. Create clean venv with only needed packages (allowlist)
    2. Run `flet pack` from inside that venv
    3. Copy Skill-bong-chay into output
    4. Validate and create zip
    """
    _print_banner("flet pack (onedir) + Cython protection")

    # Step 1: Create/verify build venv
    if not skip_venv:
        create_build_venv(force=False)
    else:
        venv_python = _get_venv_python()
        if not os.path.exists(venv_python):
            print("  No build venv found! Run 'python build.py pack' first.")
            sys.exit(1)
        print("[1/5] Using existing build venv (quick mode)")

    # Step 2: Run flet pack from venv
    print("\n[2/5] Packaging with flet pack (inside clean venv)...")

    venv_python = _get_venv_python()

    cmd = [
        venv_python, "-c", "from flet.cli import main; main()",
        "pack",
        MAIN_SCRIPT,
        "--name", APP_NAME,
        "--distpath", OUTPUT_DIR,
        "--product-name", PRODUCT_NAME,
        "--file-description", FILE_DESCRIPTION,
        "--product-version", PRODUCT_VERSION,
        "--file-version", FILE_VERSION,
        "--company-name", COMPANY_NAME,
        "--copyright", COPYRIGHT,
        "--onedir",  # Always onedir — better UX, faster startup
        "-y",
        # Hidden imports for dynamically imported modules in Skill-bong-chay
        "--hidden-import", "google.generativeai",
        "--hidden-import", "dotenv",
        "--hidden-import", "google.ai.generativelanguage",
        "--hidden-import", "google.api_core",
        "--hidden-import", "google.auth",
        "--hidden-import", "proto",
        "--hidden-import", "grpc",
    ]

    if os.path.exists(ICON_PATH):
        cmd.extend(["-i", ICON_PATH])

    _run(cmd, "Running flet pack...")

    # Locate output directory
    dist_dir = os.path.join(OUTPUT_DIR, APP_NAME)
    if not os.path.isdir(dist_dir):
        # flet pack may output to dist/main/ — rename
        for alt_name in ["main", MAIN_SCRIPT.replace(".py", "")]:
            alt = os.path.join(OUTPUT_DIR, alt_name)
            if os.path.isdir(alt):
                os.rename(alt, dist_dir)
                break

    if not os.path.isdir(dist_dir):
        print(f"  Expected output dir not found: {dist_dir}")
        print(f"  dist/ contents:")
        for item in os.listdir(OUTPUT_DIR):
            print(f"    {item}")
        sys.exit(1)

    # Step 3: Copy Skill-bong-chay
    print("\n[3/5] Copying pipeline scripts...")
    _copy_skills(dist_dir)

    # Step 4: Cython protection — compile .py -> .pyd
    print("\n[4/5] Protecting source code (Cython .py -> .pyd)...")
    _protect_with_cython(dist_dir)

    # Step 5: Validate
    print("\n[5/5] Validating build...")
    _validate_build(dist_dir)

    _print_success(dist_dir, "flet pack (onedir) + Cython protection")
    _make_zip(dist_dir)


# ─── Cython Protection ────────────────────────────────────────

def _protect_with_cython(dist_dir: str) -> None:
    """Compile Skill-bong-chay .py files to .pyd using Cython.

    .pyd files are native C extensions — cannot be decompiled back to source.
    This protects prompts, agent logic, and pipeline orchestration.
    """
    compile_script = os.path.join(APP_DIR, "compile_protect.py")
    if not os.path.exists(compile_script):
        print("  WARNING: compile_protect.py not found, skipping protection")
        return

    result = subprocess.run(
        [sys.executable, compile_script, dist_dir],
        cwd=APP_DIR,
    )
    if result.returncode != 0:
        print("  WARNING: Cython protection had errors (build continues)")


# ─── Build: flet build windows (Flutter native) ──────────────

def build_native() -> None:
    """Build using `flet build windows` — Flutter native build.

    This creates a proper Windows application with:
    - Compiled .pyc (--compile-app) — harder to decompile
    - Cleaned up source files (--cleanup-app) — no .py in output
    - Better antivirus compatibility (Flutter-based, not PyInstaller)

    Requires: Flutter SDK installed and in PATH.
    """
    _print_banner("flet build windows (native)")

    # Check Flutter SDK
    try:
        subprocess.run(["flutter", "--version"], capture_output=True, check=True, timeout=15)
    except (FileNotFoundError, subprocess.SubprocessError):
        print("  Flutter SDK not found in PATH!")
        print()
        print("  To install Flutter SDK:")
        print("    1. Download: https://flutter.dev/docs/get-started/install/windows")
        print("    2. Extract to C:\\flutter")
        print("    3. Add C:\\flutter\\bin to PATH")
        print("    4. Run: flutter doctor")
        print()
        print("  Or use 'python build.py pack' instead (no Flutter needed)")
        sys.exit(1)

    print("[1/3] Building with flet build windows...")

    cmd = [
        sys.executable, "-c", "from flet.cli import main; main()",
        "build", "windows",
        "--project", APP_NAME.lower(),
        "--product", PRODUCT_NAME,
        "--company", COMPANY_NAME,
        "--copyright", COPYRIGHT,
        "--description", FILE_DESCRIPTION,
        "--build-version", PRODUCT_VERSION.replace(".0", "").rstrip("."),
        # Code protection
        "--compile-app",
        "--compile-packages",
        "--cleanup-app",
        "--cleanup-packages",
        # Exclude unnecessary files
        "--exclude", "__pycache__", "*.pyc", ".git", ".env",
        "--yes",
    ]

    _run(cmd, "Running flet build windows...")

    build_dir = os.path.join(APP_DIR, "build", "windows")
    if not os.path.isdir(build_dir):
        print(f"  Build output not found: {build_dir}")
        sys.exit(1)

    print("\n[2/3] Copying to dist/ and adding pipeline scripts...")
    final_dir = os.path.join(OUTPUT_DIR, APP_NAME)
    if os.path.exists(final_dir):
        shutil.rmtree(final_dir)
    shutil.copytree(build_dir, final_dir)
    _copy_skills(final_dir)

    print("\n[3/3] Validating build...")
    _validate_build(final_dir)

    _print_success(final_dir, "flet build windows (compiled + cleaned)")
    _make_zip(final_dir)


# ─── Validation ───────────────────────────────────────────────

def _validate_build(dist_dir: str) -> None:
    """Check that the build output is correct and not bloated."""
    issues = []

    # Check exe exists
    exe_name = f"{APP_NAME}.exe"
    exe_path = os.path.join(dist_dir, exe_name)
    alt_exe = os.path.join(dist_dir, "main.exe")

    if os.path.exists(exe_path):
        print(f"  OK {exe_name} found ({os.path.getsize(exe_path) / 1024 / 1024:.1f} MB)")
    elif os.path.exists(alt_exe):
        os.rename(alt_exe, exe_path)
        print(f"  OK Renamed main.exe -> {exe_name}")
    else:
        issues.append(f"  MISSING: {exe_name}")

    # Check Skill-bong-chay
    skill_dir = os.path.join(dist_dir, "Skill-bong-chay")
    if os.path.isdir(skill_dir):
        py_count = sum(1 for f in os.listdir(skill_dir) if f.endswith(".py"))
        print(f"  OK Skill-bong-chay/ found ({py_count} .py files)")
    else:
        issues.append("  MISSING: Skill-bong-chay/")

    # Check for bloat (key indicator: if torch is present, something went wrong)
    internal_dir = os.path.join(dist_dir, "_internal")
    if os.path.isdir(internal_dir):
        bloat_markers = ["torch", "scipy", "sklearn", "tensorflow", "pandas"]
        for marker in bloat_markers:
            marker_path = os.path.join(internal_dir, marker)
            if os.path.isdir(marker_path):
                issues.append(f"  BLOAT: {marker}/ found in _internal/ — venv may be contaminated!")

    # Check total size — should be under 200 MB
    total_size = _folder_size(dist_dir)
    total_mb = total_size / 1024 / 1024
    if total_mb > 500:
        issues.append(f"  BLOAT: Total size is {total_mb:.0f} MB (expected < 200 MB)")
        issues.append("         Run 'python build.py clean' and rebuild")
    elif total_mb > 200:
        print(f"  WARNING: Total size is {total_mb:.0f} MB (target < 200 MB)")
    else:
        print(f"  OK Total size: {total_mb:.0f} MB")

    # Check for .env leak
    for root, _, files in os.walk(dist_dir):
        for f in files:
            if f == ".env":
                env_path = os.path.join(root, f)
                os.remove(env_path)
                print(f"  REMOVED leaked .env: {os.path.relpath(env_path, dist_dir)}")

    if issues:
        print()
        for issue in issues:
            print(issue)
        print()
        print("  Build may be incomplete or bloated!")


# ─── Clean ────────────────────────────────────────────────────

def clean() -> None:
    """Remove all build artifacts including the build venv."""
    dirs_to_clean = [
        os.path.join(APP_DIR, OUTPUT_DIR),
        os.path.join(APP_DIR, BUILD_VENV),
        os.path.join(APP_DIR, "build"),
        os.path.join(APP_DIR, "__pycache__"),
    ]
    files_to_clean = [
        os.path.join(APP_DIR, f"{APP_NAME}.spec"),
        os.path.join(APP_DIR, "nuitka-crash-report.xml"),
    ]

    for d in dirs_to_clean:
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f"  Removed {os.path.relpath(d, APP_DIR)}/")

    for f in files_to_clean:
        if os.path.isfile(f):
            os.remove(f)
            print(f"  Removed {os.path.basename(f)}")

    print("\n  Clean complete. Run 'python build.py' to rebuild from scratch.")


# ─── Main ─────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    start = time.time()

    mode = sys.argv[1] if len(sys.argv) > 1 else "pack"

    if mode in ("pack", "build"):
        build_pack(skip_venv=False)
    elif mode == "quick":
        build_pack(skip_venv=True)
    elif mode == "native":
        build_native()
    elif mode == "clean":
        clean()
    elif mode == "venv":
        # Just create the venv without building
        create_build_venv(force=True)
    else:
        print(f"Unknown mode: {mode}")
        print()
        print("Usage:")
        print("  python build.py              # Full build (create venv + pack)")
        print("  python build.py pack         # Same as above")
        print("  python build.py quick        # Reuse existing venv (faster)")
        print("  python build.py native       # flet build windows (needs Flutter)")
        print("  python build.py venv         # Only create/recreate build venv")
        print("  python build.py clean        # Remove everything (venv + dist)")
        sys.exit(1)

    elapsed = time.time() - start
    print(f"\n  Total time: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
