# Local first, no deeper tie to one model vendor

Admiralty keeps everything it produces on the Player's machine: Snapshots, Briefings, Solution Graphs, Debriefs and the Player Model. It publishes nothing to a hosted service, including Claude Artifacts; access from another device, an archive of old Briefings and comments on a graph can all be built locally, and storing them with a vendor adds nothing. The graph page ships its libraries and font with the plugin, so it opens offline and no third party sees it opened. The core stays a Python package that needs no language model: extraction, the Mechanics and Solution Graphs, the Unverified Claim check and the graph page run on their own. Everything tied to one agent host lives at the edge, in the skills, the hooks and the MCP server. MCP is an open protocol other hosts speak too.

## Consequences

The long-term direction is to run on other agent hosts as well (Codex, Cursor); moving there means rewriting skills and hooks, not the package. No such move is planned yet, but new work does not tie Admiralty closer to Claude Code: no Artifacts or other hosted Claude features, and host-specific inputs (such as the Stop hook's JSON) are read in one place each.
