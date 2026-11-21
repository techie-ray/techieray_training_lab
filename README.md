# techieray training lab

**Training sets for AI and technology law, built to be used as reinforcement learning environments.**

techieray training lab provides training sets for AI and technology law use cases, such as regulatory research,
contract negotiation, compliance analysis, and policy and governance work. Each training set gives an AI system tasks
to complete, checked answers and a reward that scores its output automatically, so it can be used as a reinforcement
learning environment or for evaluation. It is built for AI labs and legal tech teams developing AI for technology law
work.

techieray training lab is provided by [techieray](https://www.techieray.com), an AI regulatory intelligence platform.
The sets here are free previews. For the full sets, email **info@techieray.com**.

## Training sets

| Domain | Set | Skill it trains | Tasks |
|---|---|---|---|
| [Regulatory research](sets/regulatory_research/README.md) | [Find primary source](sets/regulatory_research/find_primary_source/README.md) | A research agent finds the official document behind news of an AI law or policy development, or recognises that none exists | 50, including 5 with no official source |

More sets and domains will follow as they are released.

## What every set includes

| Part | What it gives you |
|---|---|
| Tasks | Questions drawn from real AI and technology law material, with checked answers |
| Automatic scoring | Code that scores each output against the checked answers, documented in the set's README |
| Tests against shortcuts | Evidence that the scoring pays for real work, not for tricks that game it |
| A datasheet | How the set was made, what it covers and its known limits |
| A data licence | The terms for using that set's data |

Where a set lets the system search or browse the web, its tools must block `techieray.com`, because techieray
publishes the source material next to its answers.

## Install

You need Python 3.10 or later. The code has no other dependencies.

```
git clone https://github.com/techie-ray/techieray_training_lab.git
cd techieray_training_lab
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

The find primary source set has an optional Claude grader. To use it, install the `grader` extra with
`pip install -e ".[grader]"`.

## Using a set

Each set has its own module, `techieray_training_lab.<domain>.<set>`, with a function to load its tasks and a way
to score an output. Its README explains the tasks, how outputs are scored and any extra rules.

To run a set on a model, use the `techieray-lab` command. For example,
`techieray-lab find-primary-source run --agent claude` runs Claude Code on your Claude plan, and `--agent codex` runs
Codex on your ChatGPT plan. The set's README explains the rules the runner applies and how to report results.

### Example from the find primary source set

The agent gets a short news alert, a jurisdiction and a date.

> Türkiye presidential decree renames national technology directorate to include AI and creates new public-sector AI
> directorate under presidency's cybersecurity body, setting data-center standards.
>
> **Türkiye, 25 December 2025**

It must return the decree as printed in Türkiye's Official Gazette. A news story about it scores nothing. Scoring
that answer looks like this.

```python
from techieray_training_lab.regulatory_research.find_primary_source import find_primary_source_reward, load_tasks

tasks = load_tasks()
task = tasks["find_primary_source-c580acab1c8f"]
answer = {"url": "https://www.resmigazete.gov.tr/eskiler/2025/12/20251225-12.pdf",
          "no_official_source": False, "confidence": "verified"}
find_primary_source_reward(task, answer).reward    # 1.0
```

## Layout

```
sets/
    regulatory_research/                  a domain, with a page listing its sets
        find_primary_source/              a set: its data, datasheet, examples and data licence
src/techieray_training_lab/               the code
    common/                               code shared across sets
    regulatory_research/
        find_primary_source/              that set's reward, grader, shortcut checks and command line
tests/
```

A new set adds a folder under its domain in both `sets/` and `src/techieray_training_lab/`. A new domain adds a
folder at the same level as `regulatory_research`, with its own page.

## Licence

The code is under the MIT licence in [LICENSE](LICENSE). Each set's data has its own licence in its folder. The
find primary source data is under CC BY-NC 4.0, which allows non-commercial use including research and evaluating AI
systems. Commercial use, including training a commercial model, needs a licence from techieray. See
[CITATION.cff](CITATION.cff) for citation details.

## Contact

For the full training sets, licensing or questions, email **info@techieray.com**.
