from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from .pipeline import run

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument('task_key', type=Path); p.add_argument('--run-id', required=True); a=p.parse_args(argv)
    r=run(json.loads(a.task_key.read_text()), run_id=a.run_id); print(json.dumps(r.__dict__, indent=2, sort_keys=True)); return 0 if r.status=='succeeded' else 1
if __name__=='__main__': sys.exit(main())
