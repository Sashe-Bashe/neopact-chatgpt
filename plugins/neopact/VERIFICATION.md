# Verification — 11 October 2026

- 20 configuration and onboarding tests passed, including identity precedence, partial environment rejection, private permissions, symlink rejection, atomic replacement, missing/malformed configuration, and credential-safe errors.
- 4 stdio protocol tests passed using the exact command from `mcp.json` and a local HTTP fixture. Buyer and seller each discover all 13 tools and successfully call `get_instructions`, `get_inbox`, and `search_catalogue`. Owner credentials and mismatched workspaces fail startup.
- Existing live Neopact connections separately passed buyer instructions/inbox and seller instructions/catalogue reads. The automated packaged-process tests use synthetic credentials and do not place orders or negotiate.
- All seven bundled Python adapter/schema files match backend commit `2e97cf701731fcdf2ce471daa6c6798d02fc2047` exactly.
- Portable manifests validate against Agent Plugins 1.0.0 JSON schemas. The subtitle is 23 characters. The logo is 180 × 180 pixels; the composer SVG is 64 × 64.
- Archive builder verifies the single plugin root, manifests, contained assets, absence of symlinks/dependency directories, and no author-specific paths or token-shaped credentials.
- Independent source review found no actionable issues.

Executed on macOS with Python 3.14.5, FastMCP 3.4.8, and MCP SDK 1.30.0. A fresh recipient installation and Windows filesystem ACL behavior have not been exercised. Direct ChatGPT web connectivity is not implemented in this local release.
