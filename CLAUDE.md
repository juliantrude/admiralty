# Hliðskjálf

Claude Code plugin plus Python package that coaches Stellaris players from save files.
Domain language: GLOSSARY.md. Plan and milestones: docs/build-plan.md. Decisions: docs/adr/.

## Commands

```
uv sync                 # needs cargo on PATH only when rust_parser must be (re)built: ~/.cargo/bin
uv run pytest           # golden tests skip when reference saves or UI values are missing
HLIDSKJALF_PERF_SLACK=1.5 uv run pytest   # on a throttled CPU (powersave): stretches time budgets
uv run ruff check . && uv run ruff format --check .
```

## Rules

- Reference saves live in `tests/fixtures/saves/<campaign>/` and never enter git (friends' player names).
  The 4.5.2 reference Campaign is `vulkan`; the Player's empire is the one played by `Plexxi`.
- Golden values come from the game UI, read by the Player. Never invent them: a golden test without a
  Player-read value stays marked as pending (`pytest.skip` with the reason).
- Never output a raw localisation key as a Display Name; an unresolvable name is an error.
- Computed values (not stored in the save) get one module each, with the formula and its game-file
  sources in the code.
