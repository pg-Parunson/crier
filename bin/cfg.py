"""One way to read config, everywhere.

The user's config.json was written by whatever version they installed; the code
reading it is whatever version they updated to. Indexing CFG["some_new_key"]
directly means every release that adds a key silences every existing user — the
hook crashes at import, exits nonzero, and nothing ever speaks again.

So: defaults first, user values on top. Nested sections (events, earcons) merge
key-by-key, so an old config keeps its choices and gains the new switches. A
corrupt config.json degrades to pure defaults instead of killing the hook —
`crier doctor` is where the corruption gets reported, not a coding session.
"""

import json
from pathlib import Path


def load(root: Path) -> dict:
    cfg = json.loads((root / "config.default.json").read_text())
    try:
        user = json.loads((root / "config.json").read_text())
    except (OSError, ValueError):
        return cfg
    for k, v in user.items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k] = {**cfg[k], **v}
        else:
            cfg[k] = v
    return cfg


def heal(root: Path) -> dict:
    """Merge and write back — config.json gains any keys this version added."""
    cfg = load(root)
    (root / "config.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    return cfg
