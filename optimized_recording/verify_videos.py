"""Run separately to avoid decoding while another module is still recording."""
import argparse
import json
from core import verify_session

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('session_folder')
    args = parser.parse_args()
    result = verify_session(args.session_folder)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['all_video_counts_match'] else 1)
