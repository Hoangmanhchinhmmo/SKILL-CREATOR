"""
Compile sensitive .py files to .pyd (native C extension) using Cython.
After compilation, .py source files are removed — only .pyd remains.
.pyd files cannot be decompiled back to source code.

Usage:
    python compile_protect.py <target_dir>

Example:
    python compile_protect.py dist/NPB-Podcast-Writer/Skill-bong-chay
    python compile_protect.py dist/NPB-Podcast-Writer/_internal
"""

import sys
import os
import shutil
import subprocess
import tempfile
import glob

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Files to compile in Skill-bong-chay/
SKILL_FILES = [
    "agents.py",
    "section_writers.py",
    "supervisor.py",
    "config.py",
    "pipeline_v2.py",
    "nlm_data.py",
    "main.py",
]

# Files to compile in app _internal/ (PyInstaller unpacked)
APP_FILES = [
    "license_service.py",
    "crypto.py",
    "machine_id.py",
]

# Files to NEVER compile (would break imports)
SKIP_FILES = ["__init__.py"]


def compile_py_to_pyd(py_path: str) -> bool:
    """Compile a single .py file to .pyd using Cython.

    Process:
    1. .py -> .c (Cython transpile)
    2. .c -> .pyd (C compiler)
    3. Delete .py and .c

    Returns True on success.
    """
    if not os.path.isfile(py_path):
        print(f"    SKIP (not found): {py_path}")
        return False

    basename = os.path.basename(py_path)
    if basename in SKIP_FILES:
        print(f"    SKIP (__init__): {basename}")
        return False

    module_name = os.path.splitext(basename)[0]
    src_dir = os.path.dirname(os.path.abspath(py_path))

    # Create a temp setup.py for this single module
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", dir=src_dir, delete=False, prefix="setup_"
    ) as f:
        setup_path = f.name
        f.write(f"""
from setuptools import setup
from Cython.Build import cythonize

setup(
    ext_modules=cythonize(
        "{basename}",
        compiler_directives={{
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
        }},
    ),
    script_args=["build_ext", "--inplace"],
)
""")

    try:
        result = subprocess.run(
            [sys.executable, setup_path, "build_ext", "--inplace"],
            cwd=src_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print(f"    FAILED: {basename}")
            if result.stderr:
                # Show last 5 lines of error
                err_lines = result.stderr.strip().split("\n")[-5:]
                for line in err_lines:
                    print(f"      {line}")
            return False

        # Find the generated .pyd file
        pyd_pattern = os.path.join(src_dir, f"{module_name}*.pyd")
        pyd_files = glob.glob(pyd_pattern)

        if not pyd_files:
            print(f"    FAILED: No .pyd generated for {basename}")
            return False

        pyd_file = pyd_files[0]
        pyd_size = os.path.getsize(pyd_file) / 1024

        # Remove original .py source
        os.remove(py_path)

        # Remove generated .c file
        c_file = os.path.join(src_dir, f"{module_name}.c")
        if os.path.exists(c_file):
            os.remove(c_file)

        print(f"    OK {basename} -> {os.path.basename(pyd_file)} ({pyd_size:.0f} KB)")
        return True

    except subprocess.TimeoutExpired:
        print(f"    TIMEOUT: {basename}")
        return False
    finally:
        # Cleanup temp setup.py
        if os.path.exists(setup_path):
            os.remove(setup_path)

        # Cleanup build/ directory created by setuptools
        build_dir = os.path.join(src_dir, "build")
        if os.path.isdir(build_dir):
            shutil.rmtree(build_dir)

        # Cleanup .egg-info
        for egg in glob.glob(os.path.join(src_dir, "*.egg-info")):
            shutil.rmtree(egg)


def compile_skill_dir(skill_dir: str) -> dict:
    """Compile all sensitive files in Skill-bong-chay/ directory."""
    print(f"\n  Compiling Skill-bong-chay/ -> .pyd")
    print(f"  Dir: {skill_dir}")

    stats = {"success": 0, "failed": 0, "skipped": 0}

    for filename in SKILL_FILES:
        py_path = os.path.join(skill_dir, filename)
        if not os.path.exists(py_path):
            stats["skipped"] += 1
            continue

        if compile_py_to_pyd(py_path):
            stats["success"] += 1
        else:
            stats["failed"] += 1

    # Also remove README.md and requirements.txt (not needed at runtime)
    for extra in ["README.md", "requirements.txt", ".gitignore"]:
        extra_path = os.path.join(skill_dir, extra)
        if os.path.exists(extra_path):
            os.remove(extra_path)
            print(f"    Removed: {extra}")

    return stats


def compile_app_services(internal_dir: str) -> dict:
    """Find and compile app service files inside PyInstaller _internal/ directory.

    PyInstaller places .pyc files in _internal/. We need to find the original
    .py files (if any) and compile them. However, in onedir mode, the .py files
    are usually already compiled to .pyc inside the PYZ archive.

    For services that are imported dynamically (like Skill-bong-chay modules),
    they exist as .py files and CAN be compiled.
    """
    stats = {"success": 0, "failed": 0, "skipped": 0}

    # In flet pack onedir, the app code is inside PYZ archive (already bytecode)
    # The main protection target is Skill-bong-chay/ which has raw .py files
    print(f"\n  Note: App services in _internal/ are already .pyc (PyInstaller PYZ)")
    print(f"  Primary protection target: Skill-bong-chay/ (done above)")

    return stats


def main():
    if len(sys.argv) < 2:
        print("Usage: python compile_protect.py <dist_dir>")
        print("Example: python compile_protect.py dist/NPB-Podcast-Writer")
        sys.exit(1)

    dist_dir = sys.argv[1]
    if not os.path.isdir(dist_dir):
        print(f"Directory not found: {dist_dir}")
        sys.exit(1)

    print("=" * 60)
    print("  Cython Protection — Compiling .py -> .pyd")
    print("=" * 60)

    # Compile Skill-bong-chay
    skill_dir = os.path.join(dist_dir, "Skill-bong-chay")
    if os.path.isdir(skill_dir):
        stats = compile_skill_dir(skill_dir)
        print(f"\n  Results: {stats['success']} compiled, {stats['failed']} failed, {stats['skipped']} skipped")
    else:
        print(f"\n  Skill-bong-chay/ not found in {dist_dir}")

    # Check app services
    internal_dir = os.path.join(dist_dir, "_internal")
    if os.path.isdir(internal_dir):
        compile_app_services(internal_dir)

    # Final listing
    if os.path.isdir(skill_dir):
        print(f"\n  Final Skill-bong-chay/ contents:")
        for f in sorted(os.listdir(skill_dir)):
            size = os.path.getsize(os.path.join(skill_dir, f)) / 1024
            ext = os.path.splitext(f)[1]
            protection = "PROTECTED (native binary)" if ext == ".pyd" else "plain text"
            print(f"    {f:40s} {size:6.0f} KB  [{protection}]")

    print()
    print("=" * 60)
    print("  Protection complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
