from pathlib import Path
import shutil
import subprocess
import sys

# Ensure project root is in sys.path for direct module imports
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.create_readme import make_readme
from scripts.generate_icons import generate_icons


def build_executable() -> None:
    dist_dir = ROOT_DIR / "dist"
    build_dir = ROOT_DIR / "build"
    icon_path = ROOT_DIR / "resources" / "icons" / "app.ico"
    tdjson_path = ROOT_DIR / "native" / "tdjson.dll"

    print("==================================================")
    print("         TMusic Desktop - Build Pipeline          ")
    print("==================================================")

    # 1. Step 1: Generate / Update README.md
    print("\n[1/4] Generating Documentation (README.md)...")
    make_readme()

    # 2. Step 2: Generate Official App Icons
    print("\n[2/4] Generating Application Icons...")
    generate_icons()

    # 3. Step 3: Clean previous build artifacts
    print("\n[3/4] Cleaning previous build artifacts...")
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # 4. Step 4: Build Executable via PyInstaller
    print("\n[4/4] Bundling Standalone Executable via PyInstaller...")
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        f"--icon={icon_path}",
        f"--add-data={ROOT_DIR / 'resources'}{sep}resources",
        f"--add-data={ROOT_DIR / 'native'}{sep}native",
        "--name=TMusic",
        "--collect-submodules=PySide6.QtMultimedia",
        "--collect-submodules=cryptography",
        str(ROOT_DIR / "app" / "main.py"),
    ]

    subprocess.check_call(cmd, cwd=str(ROOT_DIR))

    # Copy native DLL directly into dist folder
    output_native = dist_dir / "TMusic" / "native"
    output_native.mkdir(parents=True, exist_ok=True)
    if tdjson_path.exists():
        shutil.copy(tdjson_path, output_native / "tdjson.dll")
        shutil.copy(tdjson_path, dist_dir / "TMusic" / "tdjson.dll")

    # Copy .env configuration if present
    env_file = ROOT_DIR / ".env"
    if env_file.exists():
        shutil.copy(env_file, dist_dir / "TMusic" / ".env")

    print("\n==================================================")
    print("🎉 Build Pipeline Completed Successfully!")
    print(f"📁 Output Directory: {dist_dir / 'TMusic'}")
    print(f"🚀 Executable:       {dist_dir / 'TMusic' / 'TMusic.exe'}")
    print("==================================================")


if __name__ == "__main__":
    build_executable()