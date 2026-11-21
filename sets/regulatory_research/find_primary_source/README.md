# Find primary source

A training set in the [regulatory research](../README.md) domain of [techieray training lab](../../../README.md).

**Can your AI agent find the actual law?**

Ask an AI research tool for the source of a new regulation and it will often hand back a news story, a law firm's
summary or the wrong government page. For lawyers and compliance teams that is not good enough. They need the
official document itself, because that is what they rely on and cite.

This repo has 50 practice tasks that train and test exactly that skill. Each task is a short news alert about an AI
law or policy development somewhere in the world. The agent must find the official document behind it, such as the
law, the bill, the decree or the regulator's decision, on the government's own site. Every task has a checked answer
key, and a reward function scores the agent's answer automatically.

The tasks come from the [Global AI Regulation Tracker](https://www.techieray.com), which a lawyer has edited every day
since 2023 and which covers 235 jurisdictions. This is a free preview of a larger training set. For the full set,
email **info@techieray.com**.

## Who it is for

| If you are | You can use it to |
|---|---|
| An AI lab | Train research agents to cite primary sources, with a reward that resists shortcuts |
| A legal tech vendor | Test whether your research tool returns the real document or just coverage of it |
| A lawyer or researcher | See for yourself how often AI tools find the actual law |

## Three example tasks

The agent sees only the alert, the jurisdiction and the date.

| Alert | Where and when | Correct answer |
|---|---|---|
| South Korean lawmakers introduce bill to amend national AI law, splitting generative AI labelling duties between model developers (machine-readable marks) and deployers (user-visible notices). | South Korea, 27 July 2026 | The bill's own page on the National Assembly's bill system, in Korean. A government press release about it scores nothing. |
| Türkiye presidential decree renames national technology directorate to include AI and creates new public-sector AI directorate under presidency's cybersecurity body, setting data-center standards. | Türkiye, 25 December 2025 | The decree as printed in the Official Gazette, a Turkish PDF |
| Kansas law takes effect voiding contract clauses that allow digital replicas of a performer's voice or likeness without specific use descriptions or legal or union representation. | Kansas, 1 January 2025 | **No official source exists.** This development never happened in Kansas. A similar law passed in another state, and citing it is wrong. |

None of the alerts names the law, gives a bill number or quotes a title, so the agent has to work out which document
is meant before it can find it.

## What makes the tasks hard

| Feature | What it means for the agent |
|---|---|
| Vague alerts | The agent has to identify the document from a description of what it does |
| Strict tasks | On 18 tasks only the authoritative text counts, meaning the enacted act, the bill text or the published instrument. The government's own press release about it scores nothing. |
| No-source tasks | 5 tasks describe a development that never happened. The right answer is that no official source exists. |
| Global coverage | 29 jurisdictions across seven regions, including five international bodies, with a cap on US tasks |
| Other languages and formats | 14 answers are not in English and 7 are PDFs |

## How good are current models?

We have not yet published results for current models on these tasks. When we do, they will appear here with the code
used to run them.

## Quick start

The reward needs Python 3.10 or later and no other packages. From the top of the repository, run these commands.

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m techieray_training_lab.regulatory_research.find_primary_source score --rollouts sets/regulatory_research/find_primary_source/examples/rollouts.jsonl
.venv/bin/python -m pytest
```

Give the agent each task's `input` (alert, jurisdictions, date) as the question, with `data/task_prompt.txt` as its
instructions. The agent answers with a URL, whether it thinks no official source exists, and how sure it is.

**One rule.** Block `techieray.com` in the agent's search and fetch tools. The tracker publishes these developments
next to their answers, so an agent that reads it is looking the answer up rather than researching it. The reward
scores those answers as wrong. `data/blocked_domains.txt` lists the domains to block.

## Run it on a model

The quickest way is to use Claude Code or Codex, on the plan you are already signed in to. You need no API key and
no other setup. From the top of the repository, after the quick start, run one of these.

```
.venv/bin/techieray-lab find-primary-source run --agent claude     # Claude Code, on your Claude plan
.venv/bin/techieray-lab find-primary-source run --agent codex      # Codex, on your ChatGPT plan
```

Then score the run with the command it prints, for example
`.venv/bin/techieray-lab find-primary-source score --rollouts runs/claude-default-default/rollouts.jsonl`.

| Option | What it does |
|---|---|
| `--model`, `--effort` | Choose the agent's model and reasoning effort. By default the agent uses its own defaults. |
| `--limit 3` | Run only the first three tasks, to try it out |
| `--rollouts 4` | Run each task four times |
| `--form input_named` | Ask the easier form of each question (see Files below) |
| `--workers` | How many tasks run at once. The default is 2, which suits a plan's usage limits. |

**Three rules, which the runner applies for you.**

1. **The agent never sees this repository.** `tasks.jsonl` holds the answer key next to each question. Each task
   runs in a new, empty temporary folder, and the agent gets only the question.
2. **The agent gets only web tools.** Claude Code gets web search and web fetch. Codex gets web search. Neither gets
   a shell, files, MCP servers, plugins, skills, hooks or your own settings. Claude Code is blocked from opening
   `techieray.com`.
3. **A rollout that saw `techieray.com` is not scored.** Neither agent can keep the site out of its search results,
   so every transcript is checked for it. A rollout that shows it is marked `blocked_domain_seen`, and `score` drops
   it. Full transcripts are kept in `transcripts/`, next to the rollouts file.

**What the results measure.** A run measures the model inside Claude Code or Codex, including that agent's own
instructions, tools and limits. It does not measure the bare model. Report results as, for example, "Claude Code
2.1, Opus 5.5, high effort", not as a score for the model alone. Each rollout records the agent, its version, the
model and the effort. Codex does not report its model, so pass `--model` if you want it recorded.

**Usage limits.** A plan has usage limits. A task that fails is not saved, and after three failures in a row the run
stops. Run the same command again once your limit resets, and it continues from where it stopped.

**Using your own setup instead.** Use the question exactly as `question()` in
`src/techieray_training_lab/regulatory_research/find_primary_source/agents.py` writes it, with `data/task_prompt.txt`
as the instructions, and follow the three rules above. Write one JSON line per answer with `example_id`, `url`,
`no_official_source` and `confidence`, and optionally `rollout_id` and `blocked_domain_seen`. Then run `score` on
that file.

## For engineers

### Calling the reward

```python
from techieray_training_lab.regulatory_research.find_primary_source import find_primary_source_reward, load_tasks

tasks = load_tasks()
answer = {"url": "https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id=202520260AB723",
          "no_official_source": False, "confidence": "verified"}
result = find_primary_source_reward(tasks["find_primary_source-3c4534e4800c"], answer)
result.reward    # 1.0, because the answer is right and marked "verified"
result.outcome   # "key"
```

### How answers are scored

The reward depends on whether the answer is right and on how sure the agent said it was.

| Answer | Agent said "verified" | Agent said "likely" | Agent said "unverified" or nothing |
|---|---|---|---|
| Correct | 1.0 | 0.9 | 0.8 |
| Certainly wrong | minus 0.25 | 0 | 0 |
| Anything else | 0 | 0 | 0 |

The gaps reward honest confidence. Saying "verified" pays off only when the agent is at least about 70% sure it is
right, so an agent that hedges every answer does worse than one that commits when it has checked. "Certainly wrong"
covers answers such as a homepage, several URLs at once or a blocked site. If the optional grader fails, the reward
is `None`, and the rollout should be dropped rather than trained on. Every result also carries an `outcome` that says
why it scored what it did, listed in `OUTCOMES`.

### What counts as the right page

Many tasks accept more than one page, such as the document itself, the issuing body's announcement and official
copies in other languages. 22 of the 45 tasks with a source accept two or more. Any accepted page scores as correct,
except on strict tasks, where only the text does.

URLs are compared after normalisation. Case, `www.`, language markers, tracking tags and known alternative addresses
for the same document are ignored, and pages under an accepted address count. For example, a bill's text tab on
congress.gov matches its main bill page, and a CELEX link and an ELI link to the same EU act match each other.

An official page that the key does not list scores 0 by default and is never penalised, because it may still be right.
To score those pages too, pass a grader. A grader is any function that takes the task and the answer and returns
`"accept"`, `"reject"` or `None`. `ClaudeGrader` in `techieray_training_lab.regulatory_research.find_primary_source.grader` is a ready
one. It needs the `grader` extra (`pip install -e ".[grader]"`) and Anthropic credentials, and you can use it with
`--grader claude`.

### Shortcut checks

The reward has been tested against fourteen shortcut strategies, such as returning the answer site's homepage, ten URLs
at once, or always saying no source exists. Every shortcut earns 0 or less on the 45 tasks that have a source. Always
saying no source exists is right only on the 5 no-source tasks, so it earns at most a tenth of the maximum overall. A
correct answer marked "verified" earns 1, and the same correct answers always marked "likely" earn 0.9.
`results/reward_checks.json` has the figures, and the `check` command reruns them.

### Files

In this folder

| Path | What it holds |
|---|---|
| `data/tasks.jsonl` | The 50 tasks, one per line |
| `data/task_prompt.txt` | Reference instructions for the agent, including the answer format |
| `data/blocked_domains.txt` | Domains the agent's tools must block |
| `examples/rollouts.jsonl` | Sample agent answers for trying the scorer |
| `results/reward_checks.json` | What each shortcut strategy earns on these tasks |
| `DATASHEET.md` | How the tasks were made, what they cover and their limits |
| `LICENSE-DATA` | The licence for this set's data |

The code is in `src/techieray_training_lab/regulatory_research/find_primary_source/` in the repository. It holds the reward, the
optional grader, the shortcut checks and the command line. URL matching and the blocked domain rule are shared by
every set and live in `src/techieray_training_lab/common/`.

Each task with a source holds the question in three forms. `input` is the vague alert, which is the intended question.
`input_named` gives the tracker's own headline, which usually names the law and is easier. `input_full` adds a short
description of the development and is easier still. The easier forms suit curriculum training or debugging. The
no-source tasks have only `input`.

## The full training set

The full set is larger and kept apart from this preview, so tasks here never appear in it. It has more strict and
no-source tasks across more jurisdictions. For access, email **info@techieray.com**.

## Licence

The data in this folder is under CC BY-NC 4.0. Non-commercial use, including research and evaluating AI systems, is
allowed with credit to "techieray training lab, find primary source set, techieray (techieray.com)". Commercial use,
including training a commercial model, needs a licence from techieray. See [LICENSE-DATA](LICENSE-DATA). The code is
under the MIT licence in the repository's [LICENSE](../../../LICENSE).
