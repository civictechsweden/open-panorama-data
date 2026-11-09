import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_SITE_URL = "https://panorama-sverige.se/"
DEFAULT_API_BASE_URL = "https://api.climateview.net/"
USER_AGENT = "panorama-downloader/1.0"
EMBEDDED_ESCAPE_REPLACEMENTS = {
    "\\u003c": "<",
    "\\u003e": ">",
    "\\u0026": "&",
}


@dataclass
class PublishedBoard:
    board_id: str
    version_id: str
    version: str
    module_urls: dict[str, str]
    updated_at: str | None


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read().decode("utf-8-sig")


def fetch_json(url: str) -> Any:
    return json.loads(fetch_text(url))


def discover_board_id(site_url: str) -> str:
    html = fetch_text(site_url)
    match = re.search(r'data-board-id="([^"]+)"', html)
    if not match:
        raise RuntimeError(f"Could not find data-board-id in {site_url}")
    return match.group(1)


def discover_api_base_url(site_url: str) -> str:
    config_url = site_url.rstrip("/") + "/api/config"
    try:
        config = fetch_json(config_url)
    except (HTTPError, URLError, json.JSONDecodeError):
        return DEFAULT_API_BASE_URL

    return config.get("azure", {}).get("proxy_base_url", DEFAULT_API_BASE_URL)


def load_published_board(site_url: str, board_id: str | None = None) -> PublishedBoard:
    resolved_board_id = board_id or discover_board_id(site_url)
    api_base_url = discover_api_base_url(site_url)
    metadata_url = (
        api_base_url.rstrip("/") + f"/published-boards/v2/{resolved_board_id}"
    )
    metadata = fetch_json(metadata_url)

    module_urls = {
        module["type"]: module.get("blobUrl")
        for module in metadata.get("content", {}).get("modules", [])
    }
    if not module_urls or not all(module_urls.values()):
        raise RuntimeError(
            f"Missing module URLs in published board metadata from {metadata_url}"
        )

    return PublishedBoard(
        board_id=resolved_board_id,
        version_id=metadata["id"],
        version=metadata["version"],
        module_urls=module_urls,
        updated_at=metadata.get("updatedAt"),
    )


def choose_output_path(output: str | None, published_board: PublishedBoard) -> Path:
    if output:
        return Path(output)
    return Path("data/panorama.json")


def normalize_embedded_escapes(value):
    if isinstance(value, dict):
        return {key: normalize_embedded_escapes(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_embedded_escapes(item) for item in value]
    if isinstance(value, str):
        normalized = value
        for escaped, unescaped in EMBEDDED_ESCAPE_REPLACEMENTS.items():
            normalized = normalized.replace(escaped, unescaped)
        return normalized
    return value


def download_board(published_board: PublishedBoard, destination: Path) -> None:
    modules = {
        module_type: fetch_json(url)
        for module_type, url in published_board.module_urls.items()
    }
    normalized_json = normalize_embedded_escapes(modules)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(normalized_json, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the current Panorama Sverige JSON snapshot."
    )
    parser.add_argument(
        "--site-url",
        default=DEFAULT_SITE_URL,
        help=f"Published Panorama site URL. Default: {DEFAULT_SITE_URL}",
    )
    parser.add_argument(
        "--board-id",
        help="Board ID override. If omitted, the script reads it from the site HTML.",
    )
    parser.add_argument(
        "--output",
        help="Output JSON path. Default: data/panorama.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    published_board = load_published_board(args.site_url, args.board_id)
    output_path = choose_output_path(args.output, published_board)
    download_board(published_board, output_path)

    print(f"Board ID:    {published_board.board_id}")
    print(f"Version:     {published_board.version}")
    print(f"Version ID:  {published_board.version_id}")
    print(f"Modules:     {', '.join(published_board.module_urls)}")
    print(f"Saved JSON:  {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
