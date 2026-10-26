# Admiralty

An AI system that helps you master Stellaris faster, from the admiral's chair:

- **Academy** coaches you while you play: a **Coach** trains you with Socratic questions.
- **Ops** consults you while you play: a **Consultant** briefs you on how to win right now.
- **Debrief** gives you feedback on a Play Session or a whole Campaign afterwards.

Formerly called Hliðskjálf (Huginn and Muninn); the design records under docs/plans and docs/adr keep the old names.

Runs as a Claude Code plugin. Reads your Stellaris save files, no game mod required.

Status: M0–M2 built (extractor and MCP server); golden values from the game UI are still pending. See:

- [GLOSSARY.md](GLOSSARY.md) for the domain language
- [docs/build-plan.md](docs/build-plan.md) for the v1 build plan
- [docs/adr/](docs/adr/) for architecture decisions
