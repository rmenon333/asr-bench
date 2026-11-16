# Working rules for Claude Code in this repo

## Who you are working with
The owner is a senior product manager, not a Python developer. They own the spec and the judgment; you write the code. Optimise for code they can read and learn from.

## How to work
1. **Read `SPEC.md` first.** Build only what it describes. If something is ambiguous or you want to add scope, ask before building.
2. **Plan, then code.** Before each build step, state the plan in 3–6 lines and wait for a go-ahead on anything non-trivial.
3. **Small steps.** One build-order step at a time. After each step, summarise what changed and how to run it, then stop.
4. **Tests first for logic.** Write or update tests for metrics, conditions and parsing. Run them and show the result before saying a step is done.
5. **Keep code simple.** Plain functions, type hints, short docstrings, no clever abstractions. Prefer the standard library and well-known packages. Ask before adding a new dependency.
6. **Teach as you go.** After each step, append a short entry to `LEARNING.md`: what each new file does, one concept explained in plain English, and one question the owner could be asked about it in an interview.
7. **Be honest in results.** Never invent numbers. If a run was partial or small, say so in the report. Report findings that contradict the hypotheses.

## Safety and hygiene
- Public data only. No customer, employer or confidential data, names or metrics anywhere in the repo.
- Never commit secrets. Keep keys in `.env` (git-ignored) and provide `.env.example`. Do not set `ANTHROPIC_API_KEY` in the shell, because that makes Claude Code bill API usage instead of the subscription.
- Never commit audio, model weights or the `data/` folder.
- Ask before running anything that downloads more than ~1 GB, installs system software, or deletes files.
- Use `uv` for Python environments (`uv sync`, `uv run`). Do not use `sudo`.

## Git
- Commit after each completed step with a clear message ("Add telephony filter with SNR tests").
- Do not push or create remote repositories unless the owner asks.

## Definition of done for any step
Code runs, tests pass, `LEARNING.md` updated, README or SPEC updated if behaviour changed, and a short "how to verify" note given to the owner.
