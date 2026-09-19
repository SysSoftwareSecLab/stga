"""Copy independent vector panels to a separately maintained JSS source.

This optional manuscript operation does not run analyses or alter LaTeX prose.
The ordinary run_all entry points do not invoke it.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

ARTWORK = {
    "fig2_repository_transport_panel_a.pdf": "Figure_2a.pdf",
    "fig2_repository_transport_panel_b.pdf": "Figure_2b.pdf",
    "fig2_volume_distribution_panel_a.pdf": "Figure_3a.pdf",
    "fig2_volume_distribution_panel_b.pdf": "Figure_3b.pdf",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--paper-dir", type=Path, required=True)
    args = parser.parse_args()
    paper_dir = args.paper_dir.resolve(strict=True)
    manuscript = (paper_dir / "JSS.tex").read_text(encoding="utf-8")
    # Validate everything before replacing any target artwork.
    for source, target in ARTWORK.items():
        data = (args.results_dir / source).read_bytes()
        if not data.startswith(b"%PDF-") or len(data) < 10_000:
            raise ValueError(f"Missing or invalid vector artwork: {source}")
        if "{" + target + "}" not in manuscript:
            raise ValueError(f"JSS.tex does not reference {target}; no files copied")
    for source, target in ARTWORK.items():
        src, dst = args.results_dir / source, paper_dir / target
        shutil.copy2(src, dst)
        digest = hashlib.sha256(dst.read_bytes()).hexdigest()
        assert digest == hashlib.sha256(src.read_bytes()).hexdigest()
        print(f"{source} -> {target}  SHA-256 {digest}")


if __name__ == "__main__":
    main()
