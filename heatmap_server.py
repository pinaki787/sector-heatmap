"""Cross-platform entrypoint for the local sector heat-map server."""
from sector_heatmap.web import run_server

if __name__ == "__main__":
    run_server()
