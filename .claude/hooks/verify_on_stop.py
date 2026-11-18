"""Claude Code Stop hook: Claude işini bitirdiğinde ilgili testleri çalıştırır.

- Python dosyaları değiştiyse backend testlerini (bellek içi SQLite ile) çalıştırır.
- frontend/ altında değişiklik varsa ve node_modules kuruluysa Vitest'i çalıştırır.
- Testler kırılırsa çıkış kodu 2 ile Claude'u durdurmaz; hata çıktısı Claude'a geri gider.
- Sonsuz döngüye girmemek için hook'un kendisi bir kez devam ettirdiyse (stop_hook_active)
  ikinci kez engellemez.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TIMEOUT_SECONDS = 600
OUTPUT_TAIL_CHARS = 4000


def repo_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path(__file__).resolve().parents[2]


def changed_files(root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    files = []
    for line in out.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        files.append(path.strip('"').replace("\\", "/"))
    return files


FULL_SUITE_TRIGGERS = ("app/database/", "app/models/", "migrations/", "tests/conftest.py", "app/main.py")


def related_tests(root: Path, files: list[str]) -> list[str] | None:
    """Değişen Python dosyalarına dokunan test dosyalarını bulur.

    None döndürürse tüm test paketi çalışır (paylaşılan altyapı değiştiğinde).
    Boş liste döndürürse çalıştırılacak ilgili test yoktur.
    """
    py_files = [f for f in files if f.endswith(".py")]
    if any(f.startswith(FULL_SUITE_TRIGGERS) for f in py_files):
        return None

    tests_dir = root / "tests"
    test_files = sorted(tests_dir.glob("test_*.py"))
    selected: set[str] = set()

    for f in py_files:
        if f.startswith("tests/test_") and (root / f).exists():
            selected.add(f)
            continue
        if not f.startswith("app/"):
            continue
        module = f[:-3].replace("/", ".")  # app/services/skill_normalizer.py -> app.services.skill_normalizer
        stem = Path(f).stem
        for test_file in test_files:
            text = test_file.read_text(encoding="utf-8", errors="ignore")
            if module in text or f"import {stem}" in text or f"{stem} import" in text:
                selected.add(test_file.relative_to(root).as_posix())

    # API'ye dokunan her değişiklikte uygulama genelini koruyan güvenlik testleri de çalışsın.
    if any(f.startswith("app/") for f in py_files):
        for name in ("tests/test_opportunity_ownership.py", "tests/test_response_headers.py"):
            if (root / name).exists():
                selected.add(name)

    return sorted(selected)


def run(cmd: list[str], cwd: Path, env: dict) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, f"{' '.join(cmd)} {TIMEOUT_SECONDS} saniyede bitmedi."
    except OSError as exc:
        return False, f"{' '.join(cmd)} çalıştırılamadı: {exc}"
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output[-OUTPUT_TAIL_CHARS:]


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}

    # Hook zaten bir kez devam ettirdiyse tekrar engelleme (sonsuz döngü koruması).
    if payload.get("stop_hook_active"):
        return 0

    root = repo_root()
    files = changed_files(root)
    if not files:
        return 0

    python_changed = any(f.endswith(".py") for f in files)
    frontend_changed = any(
        f.startswith("frontend/") and not f.startswith("frontend/node_modules/")
        for f in files
    )

    failures = []

    if python_changed:
        env = dict(os.environ)
        env["DATABASE_URL"] = "sqlite:///:memory:"
        env["PYTHON_DOTENV_DISABLED"] = "1"
        targets = related_tests(root, files)
        if targets is None:
            cmd = [sys.executable, "-m", "pytest", "-q", "-x"]
        elif not targets:
            cmd = None
        else:
            cmd = [sys.executable, "-m", "pytest", "-q", "-x", *targets]
        if cmd is None:
            ok, output = True, ""
        else:
            ok, output = run(cmd, root, env)
        if not ok:
            failures.append(("Backend testleri (pytest)", output))

    if frontend_changed:
        frontend = root / "frontend"
        npm = shutil.which("npm")
        if npm and (frontend / "node_modules").is_dir():
            ok, output = run([npm, "test"], frontend, dict(os.environ))
            if not ok:
                failures.append(("Frontend testleri (vitest)", output))

    if not failures:
        return 0

    lines = [
        "Testler kırık; işi bitmiş sayma. Kodu düzelt (testi değiştirme, atlama veya sleep ekleme).",
        "Aynı hata üç turda düzelmezse dur ve kullanıcıya sor.",
        "",
    ]
    for name, output in failures:
        lines.append(f"--- {name} ---")
        lines.append(output.strip())
        lines.append("")
    print("\n".join(lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
