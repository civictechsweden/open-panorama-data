import argparse
import json
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a Panorama JSON snapshot to CSV."
    )
    parser.add_argument(
        "input_json",
        nargs="?",
        help="Path to the downloaded JSON file. Default: data/panorama.json if present, otherwise newest data_*.json.",
    )
    parser.add_argument(
        "--output-stem",
        help="Output filename stem. Default: data/panorama.",
    )
    return parser.parse_args()


def resolve_input_path(input_json: str | None) -> Path:
    if input_json:
        path = Path(input_json)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        return path

    default_path = Path("data/panorama.json")
    if default_path.exists():
        return default_path

    candidates = sorted(Path(".").glob("data_*.json"))
    if not candidates:
        raise FileNotFoundError(
            "Could not find data/panorama.json or any data_*.json files in the current directory."
        )
    return candidates[-1]


def build_output_stem(input_path: Path, output_stem: str | None) -> Path:
    if output_stem:
        return Path(output_stem)
    return Path("data/panorama")


def convert_snapshot(input_path: Path, output_stem: Path) -> Path:
    with input_path.open(encoding="utf-8") as json_data:
        data = json.load(json_data)

    board_data = data["content"]["boardData"]["board"]["data"]

    def get_type(type_id):
        if not type_id:
            return None
        matches = [
            t["displayValue"]
            for t in board_data["actionTypes"]
            if t["id"] == type_id
        ]
        return matches[0] if matches else type_id

    def get_tag(tag_id):
        if not tag_id:
            return None
        matches = [
            t["displayValue"] for t in board_data["actionTags"] if t["id"] == tag_id
        ]
        return matches[0] if matches else tag_id

    def get_tags(tag_ids):
        if tag_ids is None:
            return []
        return [get_tag(tag_id) for tag_id in tag_ids]

    def get_status(status_id):
        if not status_id:
            return None
        matches = [
            s["displayValue"]
            for s in board_data["actionStatuses"]
            if s["id"] == status_id
        ]
        return matches[0] if matches else status_id

    actions = data["content"]["entityData"]["actions"]
    actions_df = pd.json_normalize(actions.values())

    actions_df["actionProperties.type"] = actions_df["actionProperties.type"].apply(
        get_type
    )
    actions_df["actionProperties.swimlane"] = actions_df[
        "actionProperties.swimlane"
    ].apply(get_status)
    actions_df["actionProperties.actionTags"] = actions_df[
        "actionProperties.actionTags"
    ].apply(get_tags)

    csv_path = output_stem.with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    actions_df.to_csv(csv_path, index=False, encoding="utf-8")
    return csv_path


def main() -> int:
    args = parse_args()
    input_path = resolve_input_path(args.input_json)
    output_stem = build_output_stem(input_path, args.output_stem)
    csv_path = convert_snapshot(input_path, output_stem)

    print(f"Input JSON:   {input_path}")
    print(f"CSV output:   {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
