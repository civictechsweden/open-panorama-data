# Open Panorama data

This little script automatically downloads raw data from the Swedish Climate Policy Council's Panorama dashboard available at [panorama-sverige.se](https://panorama-sverige.se) and makes it available in its original JSON format as well as a tabular CSV format:

- [data/panorama.json](https://raw.githubusercontent.com/civictechsweden/open-panorama-data/refs/heads/main/data/panorama.json)
- [data/panorama.csv](https://raw.githubusercontent.com/civictechsweden/open-panorama-data/refs/heads/main/data/panorama.csv)

This dashboard contains very important information about Sweden's emissions and policy actions for a green transition. The goal is to make the underlying data more available for further analysis.

The data is updated every Monday at 01:00 AM UTC.

## Instructions

1. Install [uv](https://docs.astral.sh/uv/getting-started/installation/).
2. Download the latest published JSON snapshot:

   ```shell
   uv run download_data.py
   ```

3. Convert the newest downloaded snapshot to CSV:

   ```shell
   uv run convert.py
   ```

4. Or run the full fetch-and-export flow in one step:

   ```shell
   uv run run.py
   ```
