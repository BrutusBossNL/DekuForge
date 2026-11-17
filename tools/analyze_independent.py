"""Inspect existing ExeFS modules read-only; write only an independent local report."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dekuforge.independent_analysis import analyze_exefs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exefs', type=Path, required=True)
    parser.add_argument('--out', type=Path, help='optional new report under this worktree local/ or build/')
    args = parser.parse_args()
    output = args.out.absolute() if args.out else None
    if output:
        if output.resolve() != output or not any(output.is_relative_to(ROOT / name) for name in ('local', 'build')):
            parser.error('Report output must be under this worktree local/ or build/, without links')
        if output.exists():
            parser.error('Report already exists; choose a new report name')
        if output.is_relative_to(args.exefs.resolve()):
            parser.error('Report must not be written inside the input module directory')
    result = analyze_exefs(args.exefs)
    encoded = json.dumps(result, indent=2) + '\n'
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as target:
            target.write(encoded)
    for module in result['modules']:
        print(f"{module['name']}: {module['supported_words']}/{module['static_text_words']} static words supported; "
              f"{module['unsupported_words']} unsupported. Not a gameplay result.")
    if output:
        print('Local report: ' + str(output))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
