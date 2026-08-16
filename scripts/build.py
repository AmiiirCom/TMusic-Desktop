import os
from pathlib import Path
import shutil
import subprocess
import sys


def build_executable() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    dist_dir = root_dir / "dist"
    build_dir = root_dir / "build"
    icon_path = root_dir / "resources" / "icons" / "app.ico"
    tdjson_path = root_dir / "native" / "tdjson.dll"

    print("==========================================")
    print("  Building TMusic Desktop Standalone EXE  ")
    print("==========================================")

    # 1. Clean previous build artifacts
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # 2. Construct PyInstaller command
    sep = ";" if sys.platform == "win32" else ":"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",  # Folder distribution for ultra-fast startup and direct DLL loading
        "--windowed",  # No black terminal window
        f"--icon={icon_path}",
        f"--add-data={root_dir / 'resources'}{sep}resources",
        f"--add-data={root_dir / 'native'}{sep}native",
        "--name=TMusic",
        "--collect-submodules=PySide6.QtMultimedia",
        "--collect-submodules=cryptography",
        str(root_dir / "app" / "main.py"),
    ]

    print("Running PyInstaller...")
    subprocess.check_call(cmd, cwd=str(root_dir))

    # 3. Ensure native DLL is also directly accessible in dist folder
    output_native = dist_dir / "TMusic" / "native"
    output_native.mkdir(parents=True, exist_ok=True)
    if tdjson_path.exists():
        shutil.copy(tdjson_path, output_native / "tdjson.dll")
        shutil.copy(tdjson_path, dist_dir / "TMusic" / "tdjson.dll")

    # 4. Copy .env template / dev config if exists
    env_file = root_dir / ".env"
    if env_file.exists():
        shutil.copy(env_file, dist_dir / "TMusic" / ".env")

    print("\n==========================================")
    print(f"🎉 Build Complete! Output directory:\n   {dist_dir / 'TMusic'}")
    print(f"Executable: {dist_dir / 'TMusic' / 'TMusic.exe'}")
    print("==========================================")


if __name__ == "__main__":
    build_executable()