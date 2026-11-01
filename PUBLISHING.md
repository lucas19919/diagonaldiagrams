# Publishing

Every step here publishes something under your name, so each one is yours to run. The order matters:
the MCP registry checks PyPI, and PyPI needs the version on GitHub first.

## 0. Before any release

```bash
py -3 tests_smoke.py              # exit 0
py -3 scripts/golden.py           # every golden figure matches, or each change is intended
py -3 scripts/build_site.py       # every gallery figure passes its audit
```

Keep the version the same in `diagonaldiagrams/__init__.py` (`__version__`), `.claude-plugin/plugin.json`, and
`server.json` (twice) and `.mcpb/manifest.json`. The tests check the first two.

## 1. GitHub: push, and turn on Pages

```bash
git push origin master
gh api repos/lucas19919/diagonaldiagrams/pages -X POST -f "source[branch]=master" -f "source[path]=/docs"
```

The site is then at https://lucas19919.github.io/diagonaldiagrams/ (a minute or two after the first build).
Pages is free for public repositories. After that, the Claude Code plugin and `pip install git+...` work for anyone.

## 2. PyPI

No token: `.github/workflows/publish.yml` uploads through PyPI trusted publishing (a publisher registered on
PyPI for this repo, that workflow and the `pypi` environment). It runs when a GitHub release is published, or by
hand from the Actions tab. Make the release with the wheel, the sdist and the desktop bundle attached:

```bash
py -3 -m build --outdir <somewhere-outside-the-repo>
py -3 scripts/build_mcpb.py       # writes dist/diagonaldiagrams-X.Y.Z.mcpb
gh release create vX.Y.Z --target master --title X.Y.Z --notes-file notes.md <wheel> <sdist> dist/*.mcpb
```

Then `pip install diagonaldiagrams` and `uvx diagonaldiagrams mcp` work. Releases go through a pull request
(version bump, CI green, squash-merge) before the tag.

## 3. Official MCP registry

Automatic: the `registry` job in `.github/workflows/publish.yml` runs after PyPI, signs in with GitHub's OIDC
identity (no code to enter) and publishes `server.json`. The registry needs step 2 first: it reads the README on
PyPI and looks for the `mcp-name:` line at the bottom of README.md. The version comes from `server.json`, so the
release bump must change it (it is one of the five version places above).

To publish by hand instead, from the folder with `server.json`:

```bash
mcp-publisher login github        # prints a code to enter at https://github.com/login/device
mcp-publisher validate            # checks server.json against the current schema
mcp-publisher publish
```

Install `mcp-publisher` from https://github.com/modelcontextprotocol/registry/releases (check the SHA-256
against the release's `checksums.txt`). If `validate` complains about a field, `mcp-publisher init` writes a fresh
server.json in the current schema; copy the fields over.

## 4. Directories that read the registry or the repo

- **Smithery** (smithery.ai): add the GitHub repo from its "add server" page.
- **Glama** (glama.ai/mcp/servers): indexes public MCP repos; claim it from the server page.
- **awesome-mcp-servers** (github.com/punkpeye/awesome-mcp-servers): one line in the README under a fitting
  section, as a pull request.
- **Anthropic's plugin directory**: submit the plugin from the Claude Code docs' "publish a plugin" page.
