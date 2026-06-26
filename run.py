from download_data import choose_output_path, download_file, load_published_board
from convert import build_output_stem, convert_snapshot


def main() -> int:
    published_board = load_published_board("https://panorama-sverige.se/")
    output_path = choose_output_path(None, published_board)
    download_file(published_board.blob_url, output_path)

    output_stem = build_output_stem(output_path, None)
    csv_path = convert_snapshot(output_path, output_stem)

    print(f"Published board: {published_board.board_id}")
    print(f"Version:         {published_board.version}")
    print(f"JSON:            {output_path}")
    print(f"CSV:             {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
