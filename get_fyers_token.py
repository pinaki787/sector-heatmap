"""Cross-platform entrypoint for interactive Fyers token renewal."""
from sector_heatmap.authentication import refresh_access_token

if __name__ == "__main__":
    refresh_access_token()
