"""Running a coding agent (Claude Code or Codex) on the tasks: isolation, answer parsing, the blocked-site audit and the
run loop. No test here calls a real agent or the network; the run loop is driven by a stand-in agent that is a tiny
Python script."""
import json
import sys
from pathlib import Path

import pytest

from techieray_training_lab.common import jsonl
from techieray_training_lab.regulatory_research.find_primary_source import agents, load_tasks
from techieray_training_lab.regulatory_research.find_primary_source.agents import (ClaudeCode, Codex, parse_answer,
                                                                                  question, run, saw_blocked_domain)
from techieray_training_lab.regulatory_research.find_primary_source.cli import score_rollouts

TASKS = load_tasks()
TURKIYE = TASKS['find_primary_source-c580acab1c8f']
KANSAS = next(t for t in TASKS.values() if t['reference']['no_official_source'])
ANSWER = {'url': 'https://www.resmigazete.gov.tr/eskiler/2025/12/20251225-12.pdf', 'no_official_source': False,
          'confidence': 'verified', 'title': 'Presidential decree'}
REPLY = 'I checked the Official Gazette.\n\n```json\n' + json.dumps(ANSWER) + '\n```'


# --- the question and the answer ---

def test_question_gives_the_alert_jurisdictions_and_date_and_nothing_from_the_key():
    q = question(TURKIYE)
    assert TURKIYE['input']['headline'] in q
    assert 'Jurisdiction(s): TR' in q and 'Date: 2025-12-25' in q
    assert 'resmigazete' not in q and 'reference' not in q


def test_question_falls_back_to_the_alert_when_a_task_has_no_easier_form():
    assert question(KANSAS, 'input_full') == question(KANSAS)


def test_parse_answer_takes_the_last_fenced_json_block():
    text = '```json\n{"url": "https://a.gov/x"}\n```\nOn reflection:\n' + REPLY
    assert parse_answer(text) == ANSWER


def test_parse_answer_accepts_a_bare_json_reply():
    assert parse_answer(json.dumps(ANSWER)) == ANSWER


def test_parse_answer_returns_none_without_an_answer_object():
    assert parse_answer('I could not find it.') is None
    assert parse_answer('```json\n{"note": 1}\n```') is None


# --- the blocked-site audit ---

@pytest.mark.parametrize('text', ['see https://www.techieray.com/x', '"domain":"techieray.com"', 'TECHIERAY.COM/tracker',
                                  'https://news.techieray.com'])
def test_saw_blocked_domain_finds_the_tracker_anywhere_in_a_transcript(text):
    assert saw_blocked_domain(text)


@pytest.mark.parametrize('text', ['mytechieray.com', 'techieray.community', 'techieray says', ''])
def test_saw_blocked_domain_ignores_other_sites(text):
    assert not saw_blocked_domain(text)


# --- isolation: what each agent is allowed to see and use ---

def test_claude_code_runs_with_web_tools_only_and_no_user_customisations():
    cmd = ClaudeCode().command('SYSTEM PROMPT', 'THE QUESTION', model='opus', effort='high')
    assert cmd[:3] == ['claude', '-p', 'THE QUESTION']
    for flag in ('--safe-mode', '--restricted', '--strict-mcp-config', '--disable-slash-commands',
                 '--no-session-persistence'):
        assert flag in cmd
    assert cmd[cmd.index('--tools') + 1] == 'WebSearch,WebFetch'
    assert cmd[cmd.index('--system-prompt') + 1] == 'SYSTEM PROMPT'
    assert cmd[cmd.index('--model') + 1] == 'opus' and cmd[cmd.index('--effort') + 1] == 'high'
    deny = json.loads(cmd[cmd.index('--settings') + 1])['permissions']['deny']
    assert 'WebFetch(domain:techieray.com)' in deny and 'WebFetch(domain:www.techieray.com)' in deny


def test_claude_code_leaves_model_and_effort_to_the_plan_default_when_not_given():
    cmd = ClaudeCode().command('S', 'Q')
    assert '--model' not in cmd and '--effort' not in cmd


def test_claude_code_bills_the_plan_not_an_api_key(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-test')
    assert 'ANTHROPIC_API_KEY' not in ClaudeCode().env()


def test_codex_runs_with_web_search_only():
    cmd = Codex().command('SYSTEM PROMPT', 'THE QUESTION', model='gpt-x', effort='high')
    assert cmd[:3] == ['codex', '--search', 'exec']
    for flag in ('--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check', '--json'):
        assert flag in cmd
    assert cmd[cmd.index('--sandbox') + 1] == 'read-only'
    disabled = {cmd[i + 1] for i, c in enumerate(cmd) if c == '--disable'}
    assert {'shell_tool', 'unified_exec', 'apps', 'plugins', 'hooks', 'browser_use', 'computer_use'} <= disabled
    assert cmd[cmd.index('-m') + 1] == 'gpt-x' and 'model_reasoning_effort="high"' in cmd
    prompt = cmd[-1]
    assert prompt.index('SYSTEM PROMPT') < prompt.index('THE QUESTION')


# --- reading each agent's transcript ---

def _lines(*events):
    return '\n'.join(json.dumps(e) for e in events) + '\n'


def test_claude_code_transcript_gives_the_final_reply_model_and_tool_use():
    out = _lines({'type': 'system', 'subtype': 'init', 'model': 'claude-opus-5-5', 'tools': ['WebFetch', 'WebSearch']},
                 {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'WebSearch', 'input': {}}]}},
                 {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'WebFetch', 'input': {}},
                                                               {'type': 'tool_use', 'name': 'WebSearch', 'input': {}}]}},
                 {'type': 'result', 'subtype': 'success', 'is_error': False, 'result': REPLY})
    t = ClaudeCode().read(out)
    assert (t.text, t.error, t.model, t.searches, t.fetches) == (REPLY, None, 'claude-opus-5-5', 2, 1)


def test_claude_code_transcript_reports_an_error_result():
    out = _lines({'type': 'result', 'subtype': 'error_during_execution', 'is_error': True,
                  'result': 'Claude usage limit reached'})
    assert 'usage limit' in ClaudeCode().read(out).error


def test_claude_code_transcript_without_a_result_is_an_error():
    assert ClaudeCode().read('').error


def test_codex_transcript_gives_the_last_message_and_searches():
    out = _lines({'type': 'thread.started', 'thread_id': 't'},
                 {'type': 'item.completed', 'item': {'type': 'web_search', 'query': 'q', 'results': []}},
                 {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'thinking aloud'}},
                 {'type': 'item.completed', 'item': {'type': 'web_search', 'query': 'q2', 'results': []}},
                 {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': REPLY}},
                 {'type': 'turn.completed', 'usage': {}})
    t = Codex().read(out)
    assert (t.text, t.error, t.searches) == (REPLY, None, 2)


@pytest.mark.parametrize('event', [{'type': 'turn.failed', 'error': {'message': 'usage limit reached'}},
                                   {'type': 'error', 'message': 'usage limit reached'}])
def test_codex_transcript_reports_a_failed_turn(event):
    assert 'usage limit' in Codex().read(_lines(event)).error


# --- the run loop, driven by a stand-in agent ---

class ScriptAgent(agents.Agent):
    """A stand-in agent: a Python one-liner whose stdout is the transcript. It prints its working folder's contents."""
    name = 'script'

    def __init__(self, reply=REPLY, fail=False, extra=''):
        self.reply, self.fail, self.extra = reply, fail, extra
        self.calls = 0

    def command(self, system, q, model=None, effort=None):
        self.calls += 1
        body = json.dumps({'reply': self.reply, 'extra': self.extra, 'fail': self.fail})
        return [sys.executable, '-I', '-c',
                'import json,os,sys; c=json.loads(sys.argv[1]); '
                'print(json.dumps({"cwd": os.getcwd(), "files": os.listdir("."), "text": c["reply"], '
                '"extra": c["extra"]})); sys.exit(3 if c["fail"] else 0)', body]

    def read(self, stdout):
        e = json.loads(stdout)
        return agents.Transcript(text=e['text'], model='stand-in-1', searches=1, fetches=0)

    def version(self):
        return 'script 1.0'


def _run(tmp_path, agent, tasks=(TURKIYE,), **kw):
    out = tmp_path / 'rollouts.jsonl'
    kw.setdefault('workers', 1)
    summary = run(list(tasks), agent, out, system='SYSTEM', **kw)
    return out, summary


def test_run_writes_one_labelled_rollout_per_task_that_the_scorer_reads(tmp_path):
    out, summary = _run(tmp_path, ScriptAgent(), effort='high')
    [row] = jsonl.read(out)
    assert row['example_id'] == TURKIYE['example_id'] and row['rollout_id'] == 1
    assert {k: row[k] for k in ANSWER} == ANSWER
    assert (row['agent'], row['agent_version'], row['model'], row['effort'], row['form']) == \
        ('script', 'script 1.0', 'stand-in-1', 'high', 'input')
    assert row['blocked_domain_seen'] is False
    [scored] = score_rollouts(list(TASKS.values()), [row])
    assert scored['reward'] == 1.0
    assert summary['written'] == 1 and summary['errors'] == 0


def test_run_works_in_a_fresh_empty_folder_outside_the_repository(tmp_path):
    out, _ = _run(tmp_path, ScriptAgent())
    transcript = json.loads((tmp_path / 'transcripts' / f"{TURKIYE['example_id']}-1.jsonl").read_text())
    assert transcript['files'] == []
    repo = Path(__file__).resolve().parent.parent
    assert not Path(transcript['cwd']).resolve().is_relative_to(repo)
    assert not Path(transcript['cwd']).exists()  # cleaned up afterwards


def test_run_skips_rollouts_already_in_the_output(tmp_path):
    agent = ScriptAgent()
    _run(tmp_path, agent, rollouts=2)
    _, summary = _run(tmp_path, agent, rollouts=3)
    assert agent.calls == 3 and summary['skipped'] == 2
    assert sorted(r['rollout_id'] for r in jsonl.read(tmp_path / 'rollouts.jsonl')) == [1, 2, 3]


def test_run_flags_a_rollout_whose_transcript_shows_the_tracker(tmp_path):
    out, summary = _run(tmp_path, ScriptAgent(extra='result from https://www.techieray.com/item/1'))
    [row] = jsonl.read(out)
    assert row['blocked_domain_seen'] is True and summary['blocked_domain_seen'] == 1


def test_run_records_an_unparseable_reply_as_unanswered(tmp_path):
    out, _ = _run(tmp_path, ScriptAgent(reply='I give up.'))
    [row] = jsonl.read(out)
    assert row['url'] is None and row['no_official_source'] is False
    [scored] = score_rollouts(list(TASKS.values()), [row])
    assert scored['outcome'] == 'unanswered'


def test_run_does_not_write_a_failed_rollout_so_a_rerun_retries_it(tmp_path):
    out, summary = _run(tmp_path, ScriptAgent(fail=True))
    assert not out.exists() or jsonl.read(out) == []
    assert summary['errors'] == 1 and summary['written'] == 0


def test_run_stops_after_repeated_failures_such_as_a_usage_cap(tmp_path):
    agent = ScriptAgent(fail=True)
    _, summary = _run(tmp_path, agent, tasks=list(TASKS.values())[:10], max_consecutive_errors=3)
    assert agent.calls == 3 and summary['stopped_early'] is True


# --- scoring respects the audit ---

def test_score_drops_a_rollout_that_saw_the_tracker():
    row = {'example_id': TURKIYE['example_id'], **ANSWER, 'blocked_domain_seen': True}
    [scored] = score_rollouts(list(TASKS.values()), [row])
    assert scored['reward'] is None and scored['outcome'] == 'blocked_domain_seen'


# --- the top-level command ---

def test_top_level_command_reaches_the_set(capsys):
    from techieray_training_lab.cli import main
    rollouts = Path(__file__).resolve().parent.parent / 'sets/regulatory_research/find_primary_source/examples/rollouts.jsonl'
    assert main(['find-primary-source', 'score', '--rollouts', str(rollouts)]) == 0
    assert json.loads(capsys.readouterr().out)['rollouts'] == 6
