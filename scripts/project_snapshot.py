#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any

# --- Check for pyyaml availability ---
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    yaml = None

# --- Windows ANSI support ---
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# --- Colors ---
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    MAGENTA = "\033[95m"
    DARK_GRAY = "\033[90m"

    @staticmethod
    def colored(text: str, color: str = "", bold: bool = False) -> str:
        bold_code = Colors.BOLD if bold else ""
        return f"{bold_code}{color}{text}{Colors.RESET}"

# --- Token Counter ---
def get_token_counter():
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return lambda text: len(enc.encode(text))
    except ImportError:
        return lambda text: len(text) // 4 + len(re.findall(r'\b\w+\b', text)) // 10

# --- Config Loader ---
def find_psconfig(start: Path) -> Optional[Path]:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for parent in [current] + list(current.parents):
        cfg = parent / "psconfig.json"
        if cfg.is_file():
            return cfg
        if parent == parent.parent:
            break
    return None

def load_config(path: Path) -> Dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(Colors.colored(f"⚠️  Warning: Failed to read config: {e}", Colors.YELLOW))
        return {}

def discover_config(script_dir: Path, user_config: Optional[Path]) -> Tuple[Dict, Path, str]:
    if user_config and user_config.is_file():
        cfg = load_config(user_config)
        root = Path(cfg.get('root', user_config.parent))
        return cfg, root, f"custom: {user_config}"

    for start in [script_dir, Path.cwd()]:
        cfg_path = find_psconfig(start)
        if cfg_path:
            cfg = load_config(cfg_path)
            if cfg:
                root = Path(cfg.get('root', cfg_path.parent))
                return cfg, root, f"psconfig.json ({cfg_path.parent})"

    return {}, script_dir.parent, "defaults"

# --- Defaults ---
DEFAULTS = {
    "output": "project_snapshot",  # Base name without extension
    "max_size": 10 * 1024 * 1024,
    "min_size": 0,
    "include_patterns": [],
    "exclude_patterns": [],
    "include_extensions": [".py", ".js", ".ts", ".json", ".md", ".txt", ".sh", ".c", ".cpp", ".h", ".java", ".go", ".rs", ".sql"],
    "exclude_extensions": [".exe", ".dll", ".so", ".pyc", ".png", ".jpg", ".zip", ".tar", ".gz", ".db", ".log"],
    "include_files": ["Dockerfile", "Makefile", ".gitignore"],
    "exclude_files": ["project_snapshot.yaml", "project_snapshot.md", ".env", "package-lock.json"],
    "exclude_dirs": [".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".idea", ".vscode"],
    "compress": False,
    "aggressive": False,
    "no_tree": False,
    "format": "yaml",  # Preferred format; will fallback to md if yaml not available
}

# --- File Filter ---
def build_filter(config: Dict):
    inc_patterns = config.get('include_patterns', DEFAULTS['include_patterns'])
    exc_patterns = config.get('exclude_patterns', DEFAULTS['exclude_patterns'])
    inc_exts = config.get('include_extensions', DEFAULTS['include_extensions'])
    exc_exts = config.get('exclude_extensions', DEFAULTS['exclude_extensions'])
    inc_files = config.get('include_files', DEFAULTS['include_files'])
    exc_files = config.get('exclude_files', DEFAULTS['exclude_files'])
    exc_dirs = config.get('exclude_dirs', DEFAULTS['exclude_dirs'])

    inc_re = [re.compile(p) for p in inc_patterns]
    exc_re = [re.compile(p) for p in exc_patterns]
    inc_exts = [e if e.startswith('.') else '.' + e for e in inc_exts]
    exc_exts = [e if e.startswith('.') else '.' + e for e in exc_exts]

    def should_include(rel_path: str) -> bool:
        if exc_re and any(p.search(rel_path) for p in exc_re):
            return False
        if inc_re and not any(p.search(rel_path) for p in inc_re):
            return False

        name = Path(rel_path).name
        ext = Path(rel_path).suffix.lower()

        if name in exc_files:
            return False
        if name in inc_files:
            return True

        if ext in exc_exts:
            return False
        if inc_exts and ext not in inc_exts:
            return False

        return True

    return should_include, set(exc_dirs)

# --- Scanner ---
def scan_project(root: Path, exclude_dirs: Set[str], should_include, min_size: int) -> List[Path]:
    files = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except (PermissionError, OSError):
            continue

        dirs = []
        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in exclude_dirs:
                        dirs.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    rel = Path(entry.path).relative_to(root).as_posix()
                    if should_include(rel):
                        try:
                            if entry.stat().st_size >= min_size:
                                files.append(Path(entry.path))
                        except OSError:
                            pass
            except OSError:
                continue

        dirs.sort(key=lambda p: p.name.lower(), reverse=True)
        stack.extend(dirs)

    files.sort(key=lambda p: p.relative_to(root).as_posix().lower())
    return files

# --- Tree (for Markdown) ---
def build_tree(root: Path, files: List[Path]) -> List[str]:
    tree = {}
    for f in files:
        parts = f.relative_to(root).parts
        node = tree
        for p in parts[:-1]:
            node = node.setdefault(p, {})
        node.setdefault('__files__', []).append(parts[-1])

    lines = []
    def render(node, prefix=''):
        items = sorted([k for k in node if k != '__files__'], key=str.lower) + sorted(node.get('__files__', []), key=str.lower)
        for i, name in enumerate(items):
            last = (i == len(items) - 1)
            connector = '└── ' if last else '├── '
            lines.append(f"{prefix}{connector}{name}")
            if name in node and name != '__files__':
                render(node[name], prefix + ('    ' if last else '│   '))
    render(tree)
    return lines

# --- Comment Stripping ---
def strip_comments(content: str, ext: str) -> str:
    lines = content.splitlines()
    out = []
    in_block = False
    for line in lines:
        if in_block:
            m = re.search(r'\*/', line)
            if m:
                line = line[m.end():]
                in_block = False
            else:
                continue

        if ext in ('.py','.sh','.bash','.rb','.go','.rs','.php','.yml','.yaml','.toml','.ini','.conf'):
            idx = line.find('#')
            if idx != -1:
                line = line[:idx]
        elif ext in ('.js','.ts','.c','.cpp','.h','.hpp','.java','.kt','.cs','.swift','.scss','.css'):
            idx = line.find('//')
            if idx != -1:
                line = line[:idx]

        start = line.find('/*')
        if start != -1:
            end = line.find('*/', start)
            if end != -1:
                line = line[:start] + line[end+2:]
            else:
                line = line[:start]
                in_block = True

        out.append(line.rstrip())
    return '\n'.join(out)

def compact_text(content: str, aggressive: bool, ext: str) -> str:
    if aggressive and ext:
        content = strip_comments(content, ext)

    lines = content.replace('\r\n','\n').replace('\r','\n').splitlines()
    cleaned = []
    prev_blank = False
    for line in lines:
        line = line.rstrip()
        if not line:
            if prev_blank:
                continue
            prev_blank = True
            cleaned.append('')
        else:
            prev_blank = False
            cleaned.append(line)
    return '\n'.join(cleaned).strip()

# --- Process File ---
def process_file(file: Path, root: Path, max_size: int, compress: bool, aggressive: bool, token_counter) -> Tuple[str, str, int, bool]:
    rel = file.relative_to(root).as_posix()
    try:
        size = file.stat().st_size
    except OSError:
        size = 0

    if size > max_size:
        return rel, f"[SKIPPED: {size/1024/1024:.2f} MB]", 0, True

    try:
        raw = file.read_text(encoding='utf-8', errors='replace')
    except OSError as e:
        return rel, f"[ERROR: {e}]", 0, True

    ext = file.suffix.lower()
    if compress:
        raw = compact_text(raw, aggressive, ext)

    if not raw.strip():
        return rel, "[EMPTY]", 0, False

    return rel, raw, token_counter(raw), False

# --- Generate YAML Snapshot ---
def generate_yaml_snapshot(root: Path, files: List[Path], max_size: int, compress: bool, aggressive: bool, no_tree: bool, token_counter) -> str:
    if not YAML_AVAILABLE:
        raise RuntimeError("pyyaml is not installed")

    total_size = sum(f.stat().st_size for f in files if f.is_file())
    ext_counts = {}
    for f in files:
        ext = f.suffix.lower() or 'no_ext'
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    # Process files in parallel
    total_tokens = 0
    file_contents = []
    with ThreadPoolExecutor(max_workers=max(4, os.cpu_count() or 4)) as executor:
        futures = {executor.submit(process_file, f, root, max_size, compress, aggressive, token_counter): f for f in files}
        for future in as_completed(futures):
            rel, content, tokens, skipped = future.result()
            if not skipped:
                total_tokens += tokens
            file_contents.append((rel, content))

    file_contents.sort(key=lambda x: x[0])

    # Build YAML structure
    data = {
        'project_snapshot': {
            'root': str(root),
            'files': len(files),
            'size': f"{total_size/1024/1024:.2f} MB",
            'extensions': dict(sorted(ext_counts.items())),
            'generated': datetime.now().isoformat()
        }
    }

    # Add tree if not no_tree
    if not no_tree:
        tree_lines = build_tree(root, files)
        data['project_snapshot']['tree'] = '\n'.join(tree_lines)

    # Add files
    data['project_snapshot']['files'] = []
    for rel, content in file_contents:
        data['project_snapshot']['files'].append({
            'path': rel,
            'content': content
        })

    # Add stats
    data['project_snapshot']['stats'] = {
        'total_tokens': total_tokens
    }

    # Convert to YAML with proper formatting
    try:
        return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False) + '\n'
    except Exception as e:
        # If YAML dump fails, fallback to JSON
        print(Colors.colored(f"⚠️  YAML dump failed: {e}. Falling back to JSON format.", Colors.YELLOW))
        return json.dumps(data, indent=2, ensure_ascii=False) + '\n'

# --- Generate Markdown Snapshot ---
def generate_markdown_snapshot(root: Path, files: List[Path], max_size: int, compress: bool, aggressive: bool, no_tree: bool, token_counter) -> str:
    total_size = sum(f.stat().st_size for f in files if f.is_file())
    ext_counts = {}
    for f in files:
        ext = f.suffix.lower() or 'no_ext'
        ext_counts[ext] = ext_counts.get(ext, 0) + 1

    output = [
        "# PROJECT SNAPSHOT",
        f"root={root}",
        f"files={len(files)}",
        f"size={total_size/1024/1024:.2f} MB",
        f"extensions={dict(sorted(ext_counts.items()))}",
        f"generated={datetime.now().isoformat()}"
    ]

    if not no_tree:
        output.append("")
        output.append("# TREE")
        output.extend(build_tree(root, files))

    output.append("")
    output.append("# FILES")

    total_tokens = 0
    results = []
    with ThreadPoolExecutor(max_workers=max(4, os.cpu_count() or 4)) as executor:
        futures = {executor.submit(process_file, f, root, max_size, compress, aggressive, token_counter): f for f in files}
        for future in as_completed(futures):
            rel, content, tokens, skipped = future.result()
            if not skipped:
                total_tokens += tokens
            results.append((rel, content))

    results.sort(key=lambda x: x[0])
    for rel, content in results:
        output.append("")
        output.append(f"[{rel}]")
        output.append(content)

    output.append("")
    output.append(f"# STATS: total_tokens≈{total_tokens}")

    return '\n'.join(output) + '\n'

# --- CLI ---
def parse_args():
    parser = argparse.ArgumentParser(description="Project Snapshot Generator v1.0.0")
    parser.add_argument('--version', action='version', version='1.0.0')
    parser.add_argument('--config', type=Path, help='Path to psconfig.json')
    parser.add_argument('--root', type=Path, help='Override project root')
    parser.add_argument('--output', type=Path, help='Override output file (base name or full path)')
    parser.add_argument('--format', choices=['yaml', 'md'], default=None,
                        help='Output format: yaml or md (default: yaml if pyyaml installed, else md)')
    parser.add_argument('--max-size', type=int, help='Override max file size in bytes')
    parser.add_argument('--min-size', type=int, help='Override min file size in bytes')
    parser.add_argument('--compress', action='store_true', help='Enable mild compression')
    parser.add_argument('--aggressive', action='store_true', help='Enable aggressive compression')
    parser.add_argument('--no-tree', action='store_true', help='Omit tree from output')
    return parser.parse_args()

# --- Main ---
def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent

    config_data, discovered_root, config_source = discover_config(script_dir, args.config)

    if args.root:
        root = args.root.resolve()
    else:
        root = discovered_root.resolve()

    if not root.is_dir():
        print(Colors.colored(f"❌ Error: root '{root}' is not a directory.", Colors.RED, bold=True))
        sys.exit(1)

    def get_val(key, default):
        if hasattr(args, key) and getattr(args, key) is not None:
            return getattr(args, key)
        return config_data.get(key, default)

    # Determine output format with fallback
    preferred_format = get_val('format', DEFAULTS['format'])
    if preferred_format == 'yaml' and not YAML_AVAILABLE:
        print(Colors.colored("⚠️  pyyaml not installed. Falling back to Markdown format.", Colors.YELLOW))
        output_format = 'md'
    else:
        output_format = preferred_format

    # Determine output path
    if args.output:
        # If user specified --output, use it as is (full path or relative)
        output_path = args.output
        if not output_path.is_absolute():
            output_path = root / output_path
        # If it has no extension or wrong extension, add based on format
        if output_path.suffix.lower() not in ['.yaml', '.yml', '.md', '.markdown']:
            ext = '.yaml' if output_format == 'yaml' else '.md'
            output_path = output_path.with_suffix(ext)
    else:
        # Use base name from config and add extension
        base_name = get_val('output', DEFAULTS['output'])
        # Remove any extension if present (to avoid double extension)
        base_name = Path(base_name).stem
        ext = '.yaml' if output_format == 'yaml' else '.md'
        output_path = root / (base_name + ext)

    max_size = get_val('max_size', DEFAULTS['max_size'])
    min_size = get_val('min_size', DEFAULTS['min_size'])
    compress = get_val('compress', DEFAULTS['compress'])
    aggressive = get_val('aggressive', DEFAULTS['aggressive'])
    no_tree = get_val('no_tree', DEFAULTS['no_tree'])

    should_include, exclude_dirs = build_filter(config_data)

    # Display header
    print()
    print(Colors.colored("╔══════════════════════════════════════════════════════════╗", Colors.CYAN, bold=True))
    print(Colors.colored("║           🚀  PROJECT SNAPSHOT GENERATOR  v1.0.0       ║", Colors.CYAN, bold=True))
    print(Colors.colored(f"║            🔥  Format: {output_format.upper():<8} (AI‑Optimized)        ║", Colors.CYAN, bold=True))
    print(Colors.colored("╚══════════════════════════════════════════════════════════╝", Colors.CYAN, bold=True))
    print()
    print(f"📂  {Colors.colored('Root:', Colors.YELLOW)} {Colors.colored(str(root), Colors.WHITE, bold=True)}")
    print(f"⚙️   {Colors.colored('Config:', Colors.YELLOW)} {Colors.colored(config_source, Colors.WHITE)}")
    print(f"📄  {Colors.colored('Format:', Colors.YELLOW)} {Colors.colored(output_format.upper(), Colors.CYAN, bold=True)}")
    if not YAML_AVAILABLE and output_format == 'md':
        print(Colors.colored("   (pyyaml not installed, using Markdown)", Colors.DARK_GRAY))
    print()

    print(Colors.colored("🔍 Scanning...", Colors.CYAN, bold=True))
    files = scan_project(root, exclude_dirs, should_include, min_size)
    print(f"   {Colors.colored(f'✅ Found {len(files)} files', Colors.GREEN)}")
    print()

    if not files:
        print(Colors.colored("⚠️  No files found. Exiting.", Colors.YELLOW, bold=True))
        return

    print(Colors.colored("📝 Generating snapshot (parallel)...", Colors.CYAN, bold=True))
    token_counter = get_token_counter()

    # Generate based on final format
    try:
        if output_format == 'yaml':
            content = generate_yaml_snapshot(root, files, max_size, compress, aggressive, no_tree, token_counter)
        else:
            content = generate_markdown_snapshot(root, files, max_size, compress, aggressive, no_tree, token_counter)
    except RuntimeError as e:
        print(Colors.colored(f"❌ Error: {e}", Colors.RED, bold=True))
        sys.exit(1)

    # If content starts with '{', it's JSON (fallback from YAML)
    if output_format == 'yaml' and content.lstrip().startswith('{'):
        output_path = output_path.with_suffix('.json')
        print(Colors.colored("   (YAML failed, saved as JSON instead)", Colors.DARK_GRAY))

    output_path.write_text(content, encoding='utf-8', newline='\n')
    out_size = output_path.stat().st_size / 1024 / 1024

    print()
    print(Colors.colored("╔══════════════════════════════════════════════════════════╗", Colors.GREEN, bold=True))
    print(Colors.colored("║                ✅  SNAPSHOT CREATED!                    ║", Colors.GREEN, bold=True))
    print(Colors.colored("╚══════════════════════════════════════════════════════════╝", Colors.GREEN, bold=True))
    print()
    print(f"📄  {Colors.colored('Output:', Colors.YELLOW)} {Colors.colored(str(output_path), Colors.WHITE, bold=True)}")
    print(f"📊  {Colors.colored('Files:', Colors.YELLOW)} {Colors.colored(str(len(files)), Colors.CYAN, bold=True)}")
    print(f"💾  {Colors.colored('Size:', Colors.YELLOW)} {Colors.colored(f'{out_size:.2f} MB', Colors.MAGENTA, bold=True)}")

    # Extract token count
    tokens = None
    if output_format == 'yaml':
        try:
            if output_path.suffix == '.json':
                data = json.loads(content)
                tokens = data['project_snapshot']['stats']['total_tokens']
            else:
                if YAML_AVAILABLE:
                    data = yaml.safe_load(content)
                    tokens = data['project_snapshot']['stats']['total_tokens']
        except Exception:
            pass
    else:
        match = re.search(r'total_tokens≈(\d+)', content)
        if match:
            tokens = int(match.group(1))

    if tokens is not None:
        print(f"🧮  {Colors.colored('Tokens:', Colors.YELLOW)} {Colors.colored(f'{tokens:,}', Colors.CYAN, bold=True)}")
    print()

if __name__ == "__main__":
    main()