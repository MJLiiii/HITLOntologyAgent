"""Run or export the explicitly synthetic engineering pilot without a live server."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from oe_studio.demo import ONTOLOGY
from oe_studio.experiments import execute_demo, execute_model
from oe_studio.settings import Settings


def export(records, path):
    fields = sorted({key for record in records for key in record})
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                             for key, value in record.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--mode', choices=['demo', 'model'], default='demo')
    parser.add_argument('--condition', choices=['A', 'B', 'C', 'D', 'all'], default='all')
    parser.add_argument('--maximum-repairs', type=int, choices=[0, 1, 2], default=2)
    parser.add_argument('--export-only', action='store_true')
    parser.add_argument('--replicates', nargs='+', type=int, default=[1])
    args = parser.parse_args()
    args.output = args.output or (Path('research/results/demo-v1') if args.mode == 'demo'
                                  else Path('research/results/model-pilot-v1') / str(uuid4()))
    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / 'runs.json'
    if args.export_only:
        records = json.loads(json_path.read_text())
    else:
        if args.mode == 'model' and json_path.exists():
            raise SystemExit('Model run outputs are immutable; choose a new output directory or --export-only.')
        runner = execute_model if args.mode == 'model' else execute_demo
        options = {'settings': Settings(), 'maximum_repairs': args.maximum_repairs} if args.mode == 'model' else {}
        records = runner(ONTOLOGY, bundle_digest=hashlib.sha256(ONTOLOGY.encode()).hexdigest(),
                         replicate_ids=args.replicates, condition=args.condition, **options)
        json_path.write_text(json.dumps(records, indent=2, sort_keys=True, allow_nan=False) + '\n')
    export(records, args.output / 'runs.csv')
    relevant = ['research/protocol.yaml', 'research/scoring-rubric.md',
                'research/data-dictionary.md', 'services/api/src/oe_studio/experiments.py']
    manifest = {'schema_version': 1, 'classification': 'synthetic_engineering_pilot_not_study_results',
                'run_count': len(records), 'scheduled_cases': sum(r['case_counts']['scheduled'] for r in records),
                'study_status': 'external_gates_pending',
                'files': {str(path): hashlib.sha256(Path(path).read_bytes()).hexdigest()
                          for path in [*relevant, json_path, args.output / 'runs.csv']}}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    waiting = sum(r['status'] == 'waiting_human' for r in records)
    print(f'{len(records)} synthetic runs exported to {args.output}; {waiting} await a human, real study gated.')
    if not args.export_only and any(r['evaluation_status'] in ('error', 'timeout', 'unsupported') for r in records):
        raise SystemExit('Results retained, but generation or evaluation failed; inspect runs.json.')


if __name__ == '__main__':
    main()
