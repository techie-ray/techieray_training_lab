"""Run a coding agent you are signed in to (Claude Code or Codex, on your own plan) on the tasks, and write rollouts
the reward can score.

  python -m techieray_training_lab.regulatory_research.find_primary_source run --agent claude
  python -m techieray_training_lab.regulatory_research.find_primary_source run --agent codex

Each rollout runs the agent once, non-interactively, in a fresh empty temporary folder, so the agent never sees this
repository or its answer key. The agent gets web search (and, for Claude Code, web fetch) and nothing else: no shell,
no file tools, no MCP servers, no plugins, skills, hooks or user settings. Claude Code is also denied fetching the
blocked sites. Neither agent can keep the blocked sites out of its search results, so every transcript is checked for
them afterwards; a rollout that saw one is marked `blocked_domain_seen` and the scorer drops it.

What this measures is the model inside that agent (its own system prompt, tools and limits), not the bare model, so
every rollout records the agent, its version, the model and the effort.

A rollout that fails (a usage cap, a crash, a timeout) is not written, so running the same command again retries it.
After several failures in a row the run stops, since that is usually a usage cap: run it again once the cap resets.
Full transcripts are kept in `transcripts/` next to the output file.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from techieray_training_lab.common import jsonl
from techieray_training_lab.common.rules import BLOCKED_DOMAINS

_JSON_BLOCK = re.compile(r'```(?:json)?\s*(\{.*?\})\s*```', re.S)
_BLOCKED = re.compile(r'(?<![a-z0-9-])(?:[a-z0-9-]+\.)*(?:' + '|'.join(re.escape(d) for d in BLOCKED_DOMAINS) +
                      r')(?![a-z0-9-])', re.I)


def question(task, form='input'):
    """The question the agent is asked: the alert, its jurisdictions and its date. Nothing from the answer key."""
    inp = task.get(form) or task['input']
    lines = [inp['headline']]
    if inp.get('excerpt'):
        lines += ['', inp['excerpt']]
    lines += ['', f"Jurisdiction(s): {', '.join(inp.get('jurisdictions') or task['input'].get('jurisdictions') or [])}",
              f"Date: {inp.get('published') or task['input'].get('published')}"]
    return '\n'.join(lines)


def _is_answer(obj):
    return isinstance(obj, dict) and ('url' in obj or 'no_official_source' in obj)


def parse_answer(text):
    """The answer object from the agent's reply: its last ```json block, or the whole reply if that is the JSON."""
    for raw in reversed(_JSON_BLOCK.findall(text or '')):
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if _is_answer(obj):
            return obj
    try:
        obj = json.loads((text or '').strip())
    except ValueError:
        return None
    return obj if _is_answer(obj) else None


def saw_blocked_domain(text):
    """True when a blocked site (or a subdomain of one) appears anywhere in the text."""
    return bool(_BLOCKED.search(text or ''))


@dataclass
class Transcript:
    """What a run of the agent produced: its final reply, or why it failed."""
    text: str = ''
    error: Optional[str] = None
    model: Optional[str] = None
    searches: int = 0
    fetches: int = 0


def _events(stdout):
    for line in (stdout or '').splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            yield e


class Agent:
    """A coding agent run once per rollout. Subclasses build the command and read its output."""
    name = ''
    binary = ''

    def command(self, system, q, model=None, effort=None):
        raise NotImplementedError

    def read(self, stdout) -> Transcript:
        raise NotImplementedError

    def env(self):
        return dict(os.environ)

    def version(self):
        try:
            return subprocess.run([self.binary, '--version'], capture_output=True, text=True,
                                  timeout=60).stdout.strip() or None
        except (OSError, subprocess.SubprocessError):
            return None

    def preflight(self):
        """(ok, message): is the agent installed and signed in?"""
        if not shutil.which(self.binary):
            return False, f'{self.binary} is not installed or not on PATH'
        return True, f'{self.binary} found'


class ClaudeCode(Agent):
    """Claude Code in print mode, on the Claude plan it is signed in to."""
    name = 'claude'
    binary = 'claude'

    def command(self, system, q, model=None, effort=None):
        deny = [f'WebFetch(domain:{d})' for b in BLOCKED_DOMAINS for d in (b, 'www.' + b)]
        cmd = [self.binary, '-p', q,
               '--system-prompt', system,
               '--safe-mode', '--restricted', '--strict-mcp-config', '--disable-slash-commands',
               '--tools', 'WebSearch,WebFetch', '--allowedTools', 'WebSearch WebFetch',
               '--settings', json.dumps({'permissions': {'deny': deny}}),
               '--no-session-persistence', '--output-format', 'stream-json', '--verbose']
        if model:
            cmd += ['--model', model]
        if effort:
            cmd += ['--effort', effort]
        return cmd

    def env(self):
        env = dict(os.environ)
        env.pop('ANTHROPIC_API_KEY', None)  # with a key set, Claude Code bills the API instead of the plan
        return env

    def read(self, stdout):
        t, result = Transcript(), None
        for e in _events(stdout):
            if e.get('type') == 'system' and e.get('subtype') == 'init':
                t.model = e.get('model')
            elif e.get('type') == 'assistant':
                for block in (e.get('message') or {}).get('content') or []:
                    if block.get('type') == 'tool_use':
                        t.searches += block.get('name') == 'WebSearch'
                        t.fetches += block.get('name') == 'WebFetch'
            elif e.get('type') == 'result':
                result = e
        if result is None:
            t.error = 'Claude Code gave no result'
        elif result.get('is_error'):
            t.error = result.get('result') or result.get('subtype') or 'Claude Code reported an error'
        else:
            t.text = result.get('result') or ''
        return t

    def preflight(self):
        ok, msg = super().preflight()
        if not ok:
            return ok, msg
        try:
            status = json.loads(subprocess.run([self.binary, 'auth', 'status'], capture_output=True, text=True,
                                               env=self.env(), timeout=60).stdout)
        except (OSError, subprocess.SubprocessError, ValueError):
            return False, 'could not read `claude auth status`'
        if not status.get('loggedIn'):
            return False, 'Claude Code is not signed in: run `claude` and sign in with your Claude plan'
        return True, f"Claude Code signed in ({status.get('authMethod')})"


class Codex(Agent):
    """Codex `exec`, on the ChatGPT plan it is signed in to, with live web search as its only tool."""
    name = 'codex'
    binary = 'codex'
    # every Codex feature that gives the model a tool other than web search
    DISABLED = ('shell_tool', 'unified_exec', 'apps', 'plugins', 'hooks', 'multi_agent', 'image_generation',
                'browser_use', 'browser_use_external', 'computer_use', 'in_app_browser', 'view_image', 'memories')

    def command(self, system, q, model=None, effort=None):
        cmd = [self.binary, '--search', 'exec',
               '--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check',
               '--sandbox', 'read-only', '--json']
        for feature in self.DISABLED:
            cmd += ['--disable', feature]
        if model:
            cmd += ['-m', model]
        if effort:
            cmd += ['-c', f'model_reasoning_effort="{effort}"']
        # Codex has no switch to replace its own instructions, so the task's instructions lead the prompt
        return cmd + [f'{system}\n\n---\n\n{q}']

    def read(self, stdout):
        t, completed, failure = Transcript(), False, None
        for e in _events(stdout):
            kind, item = e.get('type'), e.get('item') or {}
            if kind == 'item.completed' and item.get('type') == 'agent_message':
                t.text = item.get('text') or ''
            elif kind == 'item.completed' and item.get('type') == 'web_search':
                t.searches += 1
            elif kind == 'turn.completed':
                completed = True
            elif kind == 'turn.failed':
                failure = (e.get('error') or {}).get('message') or 'Codex turn failed'
            elif kind == 'error':
                failure = e.get('message') or 'Codex reported an error'
        if failure and not (completed and t.text):
            t.error = failure
        elif not completed:
            t.error = 'Codex did not finish its turn'
        return t

    def preflight(self):
        ok, msg = super().preflight()
        if not ok:
            return ok, msg
        try:
            p = subprocess.run([self.binary, 'login', 'status'], capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return False, 'could not read `codex login status`'
        status = (p.stdout + p.stderr).strip()
        if p.returncode != 0 or 'not logged in' in status.lower():
            return False, 'Codex is not signed in: run `codex login` and sign in with your ChatGPT plan'
        return True, f'Codex: {status}'


AGENTS = {'claude': ClaudeCode, 'codex': Codex}


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def run(tasks, agent, out, system, *, form='input', rollouts=1, model=None, effort=None, workers=2, timeout=1800,
        max_consecutive_errors=3, log=_log):
    """Run `agent` on each task `rollouts` times, appending one line per finished rollout to `out`."""
    out = Path(out)
    transcripts = out.parent / 'transcripts'
    transcripts.mkdir(parents=True, exist_ok=True)
    done = {(r['example_id'], r.get('rollout_id')) for r in (jsonl.read(out) if out.exists() else [])}
    todo = [(t, i) for t in tasks for i in range(1, rollouts + 1) if (t['example_id'], i) not in done]
    version = agent.version()
    log(f'{len(todo)} rollouts to run ({len(done)} already in {out}); agent {agent.name} ({version}), '
        f'model {model or "default"}, effort {effort or "default"}, form {form}')

    lock, stop = threading.Lock(), threading.Event()
    counts = {'written': 0, 'errors': 0, 'blocked_domain_seen': 0, 'consecutive_errors': 0}

    def one(task, rid):
        if stop.is_set():
            return
        key = f"{task['example_id']}-{rid}"
        with tempfile.TemporaryDirectory(prefix='fps-') as workdir:
            try:
                proc = subprocess.run(agent.command(system, question(task, form), model, effort), cwd=workdir,
                                      env=agent.env(), stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                      timeout=timeout)
                stdout, code, stderr = proc.stdout, proc.returncode, proc.stderr
            except subprocess.TimeoutExpired as e:
                stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
                code, stderr = None, f'timed out after {timeout}s'
        (transcripts / f'{key}.jsonl').write_text(stdout, encoding='utf-8')
        t = agent.read(stdout)
        error = t.error or (None if code == 0 else f'exit {code}: {(stderr or "").strip()[-300:]}')
        with lock:
            if error:
                counts['errors'] += 1
                counts['consecutive_errors'] += 1
                log(f'  ERROR {key}: {error} (not written; run again to retry)')
                if counts['consecutive_errors'] >= max_consecutive_errors:
                    stop.set()
                return
            counts['consecutive_errors'] = 0
            answer = parse_answer(t.text) or {}
            seen = saw_blocked_domain(stdout)
            row = {'example_id': task['example_id'], 'rollout_id': rid, 'url': answer.get('url'),
                   'no_official_source': bool(answer.get('no_official_source')),
                   'confidence': answer.get('confidence'), 'title': answer.get('title'),
                   'agent': agent.name, 'agent_version': version, 'model': t.model or model, 'effort': effort,
                   'form': form, 'searches': t.searches, 'fetches': t.fetches, 'blocked_domain_seen': seen}
            with open(out, 'a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')
            counts['written'] += 1
            counts['blocked_domain_seen'] += seen
        result = row['url'] or ('no official source' if row['no_official_source'] else 'no answer')
        log(f"  {key}: {t.searches} searches, {t.fetches} fetches -> {result} [{row['confidence']}]"
            + (' BLOCKED SITE SEEN, will not be scored' if seen else ''))

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for f in [pool.submit(one, t, i) for t, i in todo]:
            f.result()
    if stop.is_set():
        log(f'Stopped after {max_consecutive_errors} failures in a row (often a usage cap). '
            'Run the same command again later to continue.')
    return {'written': counts['written'], 'errors': counts['errors'], 'skipped': len(done),
            'blocked_domain_seen': counts['blocked_domain_seen'], 'stopped_early': stop.is_set()}
