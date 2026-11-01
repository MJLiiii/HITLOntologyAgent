"""Evaluate externally frozen outputs against an evaluator-owned held-out mount."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from research.evaluator import EvaluatorIdentity, evaluate_frozen  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--credential-file', type=Path, required=True)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--app-data-dir', type=Path, default=ROOT / '.data')
    args = parser.parse_args()
    identity = EvaluatorIdentity(args.subject, 'evaluator', args.credential_file.read_bytes())
    _, path = evaluate_frozen(args.input_dir, args.output_dir, identity,
                              forbidden_roots=[ROOT, args.app_data_dir])
    print(f'Evaluator report saved in the private output mount: {path.name}')


if __name__ == '__main__':
    main()
