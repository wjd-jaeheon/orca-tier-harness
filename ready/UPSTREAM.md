# ready (vendored from dryforge)

- Source: https://github.com/prekuter/dryforge, `src/skills/ready/` (MIT, see LICENSE in this directory)
- Version: vv1.1.1, commit c950599d463d083a48e49c6dc1207904cf0c4374
- `READY.md` is the upstream `SKILL.md` renamed so that no runtime registers it as a standalone skill. Contents are unmodified; tier-harness overrides live in `../SKILL.md` §3.

Re-sync:

```text
git clone --depth 1 https://github.com/prekuter/dryforge /tmp/dryforge
rm -rf ready/references && cp -r /tmp/dryforge/src/skills/ready/references ready/references
cp /tmp/dryforge/src/skills/ready/SKILL.md ready/READY.md && cp /tmp/dryforge/LICENSE ready/LICENSE
git -C /tmp/dryforge rev-parse HEAD   # update the commit above
```
