from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def try_export_pdf(pptx_path: Path, output_dir: Path) -> Path | None:
    """Best-effort local preview export. Works when LibreOffice is available."""
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(output_dir), str(pptx_path)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
        pdf = output_dir / f"{pptx_path.stem}.pdf"
        return pdf if pdf.exists() else None
    except Exception:
        return None
