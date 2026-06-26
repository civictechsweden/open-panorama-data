import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
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
    blob_url: str
    updated_at: str | None


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str) -> dict:
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
    metadata_url = api_base_url.rstrip("/") + f"/published-boards/v2/{resolved_board_id}"
    metadata = fetch_json(metadata_url)

    blob_url = metadata.get("content", {}).get("oldBlobUrl") or metadata.get("blobUrl")
    if not blob_url:
        raise RuntimeError(f"Missing blob URL in published board metadata from {metadata_url}")

    return PublishedBoard(
        board_id=resolved_board_id,
        version_id=metadata["id"],
        version=metadata["version"],
        blob_url=blob_url,
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


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request) as response:
        payload = response.read().decode("utf-8-sig")
        normalized_json = normalize_embedded_escapes(json.loads(payload))
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
    download_file(published_board.blob_url, output_path)

    print(f"Board ID:    {published_board.board_id}")
    print(f"Version:     {published_board.version}")
    print(f"Version ID:  {published_board.version_id}")
    print(f"Blob URL:    {published_board.blob_url}")
    print(f"Saved JSON:  {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
