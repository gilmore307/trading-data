from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_PATH = ROOT / 'config' / 'etf_proxy_universe.json'


def main() -> None:
    payload = json.loads(OUT_PATH.read_text(encoding='utf-8'))
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
