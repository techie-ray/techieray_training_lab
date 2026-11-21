"""Command line for the regulatory research set.

  python -m techieray_training_lab.regulatory_research.find_primary_source score --items TASKS --rollouts ROLLOUTS [--out REWARDS]
  python -m techieray_training_lab.regulatory_research.find_primary_source score ... --grader claude   # needs the [grader] extra
  python -m techieray_training_lab.regulatory_research.find_primary_source check --items TASKS         # rerun the shortcut checks
  python -m techieray_training_lab.regulatory_research.find_primary_source run --agent claude|codex    # run an agent on your plan (agents.py)

`--items` defaults to the set's own tasks when the package runs from this repository.

Rollouts are JSON Lines, one answer per line: {"example_id", "url", "no_official_source", "confidence"}, plus an
optional "rollout_id" (several rollouts per example are fine). Each output line is the rollout's ids with its
reward, outcome and penalised flag. The summary says which grader mode produced the rewards. A rollout marked
`blocked_domain_seen` (its transcript showed a blocked site) is not scored: its reward is None.
"""
import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from techieray_training_lab.common import jsonl
from techieray_training_lab.regulatory_research.find_primary_source.reward import find_primary_source_reward


def grader_mode(grader):
    return 'Claude grader for unlisted URLs' if grader == 'claude' else 'key only; unlisted URLs score 0'


def score_rollouts(items, rollouts, grader=None, workers=8):
    by_id = {r['example_id']: r for r in items}

    def one(rollout):
        item = by_id.get(rollout.get('example_id'))
        if item is None:
            return {'example_id': rollout.get('example_id'), 'rollout_id': rollout.get('rollout_id'),
                    'reward': None, 'outcome': 'unknown_example', 'penalised': False, 'correct': None}
        if rollout.get('blocked_domain_seen'):
            return {'example_id': item['example_id'], 'rollout_id': rollout.get('rollout_id'),
                    'reward': None, 'outcome': 'blocked_domain_seen', 'penalised': False, 'correct': None}
        result = find_primary_source_reward(item, rollout, grader)
        return {'example_id': item['example_id'], 'rollout_id': rollout.get('rollout_id'), **result.to_dict()}

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(one, rollouts))


def summarise(rows, mode):
    scored = [r['reward'] for r in rows if r['reward'] is not None]
    return {'rollouts': len(rows), 'scored': len(scored),
            'mean_reward': round(sum(scored) / len(scored), 4) if scored else None,
            'solved': sum(bool(r['correct']) for r in rows), 'penalised': sum(r['penalised'] for r in rows),
            'outcomes': dict(Counter(r['outcome'] for r in rows).most_common()), 'grader_mode': mode}


def run_agent(a):
    from techieray_training_lab.regulatory_research.find_primary_source import agents
    agent = agents.AGENTS[a.agent]()
    ok, msg = agent.preflight()
    print(msg, file=sys.stderr)
    if not ok:
        return 1
    tasks = jsonl.read(a.items)
    if a.ids:
        tasks = [t for t in tasks if t['example_id'] in set(a.ids)]
    if a.limit:
        tasks = tasks[:a.limit]
    out = a.out or Path('runs') / f"{a.agent}-{a.model or 'default'}-{a.effort or 'default'}" / 'rollouts.jsonl'
    system = (a.items.parent / 'task_prompt.txt').read_text(encoding='utf-8').strip()
    summary = agents.run(tasks, agent, out, system, form=a.form, rollouts=a.rollouts, model=a.model,
                         effort=a.effort, workers=a.workers, timeout=a.timeout)
    print(json.dumps({**summary, 'out': str(out)}, indent=2))
    print(f'Score it with: techieray-lab find-primary-source score --rollouts {out}', file=sys.stderr)
    return 1 if summary['stopped_early'] else 0


TASKS = Path(__file__).resolve().parents[4] / 'sets' / 'regulatory_research' / 'find_primary_source' / 'data' / 'tasks.jsonl'


def main(argv=None, prog=None):
    p = argparse.ArgumentParser(prog=prog, description=__doc__.split('\n\n')[0])
    sub = p.add_subparsers(dest='cmd', required=True)
    ps = sub.add_parser('score', help='score a file of rollouts')
    ps.add_argument('--items', type=Path, default=TASKS, help="tasks file with the answer key (default: this set's tasks.jsonl)")
    ps.add_argument('--rollouts', required=True, type=Path)
    ps.add_argument('--out', type=Path)
    ps.add_argument('--grader', choices=['none', 'claude'], default='none')
    ps.add_argument('--workers', type=int, default=8)
    pc = sub.add_parser('check', help='run the shortcut strategies against the reward')
    pc.add_argument('--items', type=Path, nargs='+', default=[TASKS], help="tasks files to check (default: this set's tasks.jsonl)")
    pr = sub.add_parser('run', help='run Claude Code or Codex on the tasks, on the plan it is signed in to')
    pr.add_argument('--agent', required=True, choices=['claude', 'codex'])
    pr.add_argument('--out', type=Path, help='rollouts file (default: runs/<agent>-<model>-<effort>/rollouts.jsonl)')
    pr.add_argument('--model', help="the agent's model name or alias (default: the agent's own default)")
    pr.add_argument('--effort', help="reasoning effort, passed to the agent (default: the agent's own default)")
    pr.add_argument('--form', default='input', choices=['input', 'input_named', 'input_full'],
                    help='which form of the question to ask (input is the intended, hardest one)')
    pr.add_argument('--rollouts', type=int, default=1, help='rollouts per task')
    pr.add_argument('--limit', type=int, help='only the first N tasks (for a smoke test)')
    pr.add_argument('--ids', nargs='+', help='only these example_ids')
    pr.add_argument('--workers', type=int, default=2, help='rollouts at once (keep low on a plan)')
    pr.add_argument('--timeout', type=int, default=1800, help='seconds before one rollout is abandoned')
    pr.add_argument('--items', type=Path, default=TASKS, help="tasks file to run (default: this set's tasks.jsonl)")
    a = p.parse_args(argv)
    if a.cmd == 'run':
        return run_agent(a)
    if a.cmd == 'check':
        from techieray_training_lab.regulatory_research.find_primary_source.checks import main as check
        return check([str(f) for f in a.items])
    grader = None
    if a.grader == 'claude':
        from techieray_training_lab.regulatory_research.find_primary_source.grader import ClaudeGrader
        grader = ClaudeGrader()
    rows = score_rollouts(jsonl.read(a.items), jsonl.read(a.rollouts), grader, a.workers)
    if a.out:
        jsonl.write(a.out, rows)
    print(json.dumps(summarise(rows, grader_mode(a.grader)), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
