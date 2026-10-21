"""Downloadable reports for one run, written to reports/<run_id>/ under the site root."""

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def zip_files(files: list[Path], out: Path, base: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, file.relative_to(base).as_posix())
    return out


def zip_dir(folder: Path, out: Path) -> Path:
    return zip_files([p for p in sorted(folder.rglob("*")) if p.is_file()], out, folder)


def copy_artifacts(tests: list[dict], raw: Path, report_dir: Path, site: Path) -> int:
    """Copy each test's trace/screenshot into the report folder and rewrite its path to be
    relative to the site root (so the dashboard can link to it). Missing files are dropped."""
    copied = 0
    for test in tests:
        kept = []
        for artifact in test["artifacts"]:
            source = raw / artifact["path"]
            if not source.is_file():
                continue
            target = report_dir / "artifacts" / artifact["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            kept.append({"type": artifact["type"], "path": target.relative_to(site).as_posix()})
            copied += 1
        test["artifacts"] = kept
    return copied


def allure_command() -> str | None:
    """ALLURE_CMD, else `allure` on PATH, else the default local install."""
    if cmd := os.getenv("ALLURE_CMD"):
        return cmd
    name = "allure.bat" if os.name == "nt" else "allure"
    if found := shutil.which(name):
        return found
    default = Path.home() / "tools" / "allure-2.46.1" / "bin" / name
    return str(default) if default.exists() else None


def allure_report_zip(results_dir: Path, out: Path) -> Path | None:
    """Generate the Allure HTML report and zip it. Returns None if Allure isn't available
    or there are no results (the build continues without this download)."""
    command = allure_command()
    if not command or not results_dir.is_dir() or not any(results_dir.iterdir()):
        return None
    env = dict(os.environ)
    if java_home := os.getenv("JAVA_HOME"):
        env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env["PATH"]
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "allure-report"
        result = subprocess.run(
            [command, "generate", str(results_dir), "-o", str(report), "--clean"],
            env=env,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0 or not (report / "index.html").exists():
            raise RuntimeError(f"allure generate failed:\n{result.stdout}\n{result.stderr}")
        return zip_dir(report, out)
