from __future__ import annotations

import argparse
import json

from ui_modules import *


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Urban renewal UI app")
    parser.add_argument(
        "--export-github-pages",
        nargs="?",
        const=str(DEFAULT_GITHUB_PAGES_EXPORT_DIR),
        metavar="OUTPUT_DIR",
        help="Export a static GitHub Pages site. Defaults to ./docs when no output dir is provided.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for the local FastAPI server.")
    parser.add_argument("--port", type=int, default=7860, help="Port for the local FastAPI server.")
    parser.add_argument(
        "--home-path",
        default="/app",
        help="Path to open from /. Use /run/setup for the lightweight upload-and-run page.",
    )
    args = parser.parse_args()

    if args.export_github_pages:
        export_result = export_github_pages_site(target_dir=args.export_github_pages)
        print(json.dumps(export_result, ensure_ascii=False, indent=2))
    else:
        import uvicorn

        uvicorn.run(create_app(home_path=args.home_path), host=args.host, port=args.port)
