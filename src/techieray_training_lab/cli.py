"""The `techieray-lab` command: `techieray-lab <set> <command> ...`, where each set has its own commands.

  techieray-lab find-primary-source run --agent claude
  techieray-lab find-primary-source score --rollouts runs/claude-default-default/rollouts.jsonl
"""
import sys
from importlib import import_module

SETS = {'find-primary-source': 'techieray_training_lab.regulatory_research.find_primary_source.cli'}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] not in SETS:
        print(__doc__.strip() + '\n\nSets: ' + ', '.join(SETS), file=sys.stderr)
        return 0 if argv[:1] in (['-h'], ['--help']) else 2
    return import_module(SETS[argv[0]]).main(argv[1:], prog=f'techieray-lab {argv[0]}')


if __name__ == '__main__':
    sys.exit(main())
