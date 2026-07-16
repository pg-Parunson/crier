#!/usr/bin/env bash
# The whole test suite. No network, no model download, no daemon — it must pass
# on a bare CI runner in seconds. Anything that needs the 200MB voice model is
# manual by design.
#
#   tests/run.sh
set -u
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$PWD"
PASS=0; FAIL=0

ok()   { PASS=$((PASS+1)); printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad()  { FAIL=$((FAIL+1)); printf '  \033[31m✗\033[0m %s\n' "$*"; }
t()    { if "$@" >/dev/null 2>&1; then ok "${DESC:-$*}"; else bad "${DESC:-$*}"; fi; }

PY="${PYTHON:-python3}"

echo "── syntax ──────────────────────────────"
DESC="bash -n bin/crier"            t bash -n bin/crier
DESC="bash -n install.sh"           t bash -n install.sh
DESC="sh -n bootstrap.sh (POSIX)"   t sh -n bootstrap.sh
if command -v dash >/dev/null; then
  DESC="dash -n bootstrap.sh"       t dash -n bootstrap.sh
fi
DESC="sh -n bin/hush.sh"            t sh -n bin/hush.sh
for f in bin/*.py; do
  DESC="pycompile $f"               t "$PY" -m py_compile "$f"
done
DESC="locales.json parses"          t "$PY" -c "import json;json.load(open('locales.json'))"
DESC="config.default.json parses"   t "$PY" -c "import json;json.load(open('config.default.json'))"

echo "── locales contract ────────────────────"
"$PY" - <<'PY' && ok "every language has all 5 levels + required keys" || bad "locales contract"
import json, sys
L = json.load(open("locales.json"))
langs = [k for k in L if isinstance(L[k], dict) and "tone_hint" in L[k]]
KEYS = ["permission_bash","permission_file","permission_other","permission_described",
        "agent_needs_input","idle","error","compact","agent_start","agent_done"]
for lang in langs:
    for lvl in "12345":
        assert lvl in L[lang], f"{lang}: missing level {lvl}"
        assert lvl in L[lang]["tone_hint"], f"{lang}: missing tone_hint {lvl}"
        for k in KEYS:
            block = L[lang][lvl]
            assert k in block and block[k], f"{lang}/{lvl}: missing {k}"
    for k in ("tools","errors","prompt","cli"):
        assert k in L[lang], f"{lang}: missing {k}"
    assert "_default" in L[lang]["errors"], f"{lang}: errors._default"
    assert set(L[lang]["cli"]["mood"]) == set("12345"), f"{lang}: cli.mood levels"
print("langs:", langs)
PY

echo "── korean numbers ──────────────────────"
if "$PY" bin/korean.py 2>/dev/null | grep -q "14/14"; then
  ok "korean.py self-test 14/14"
else
  bad "korean.py self-test"
fi

echo "── announce.py (sandboxed) ─────────────"
"$PY" - "$ROOT" <<'PY' && ok "announce unit suite" || bad "announce unit suite"
import importlib.util, json, pathlib, shutil, sys, tempfile

root = pathlib.Path(sys.argv[1])
tmp = pathlib.Path(tempfile.mkdtemp(prefix="crier-test-"))
(tmp / "bin").mkdir()
for f in ("announce.py", "audio.py", "korean.py", "cfg.py"):
    shutil.copy2(root / "bin" / f, tmp / "bin" / f)
shutil.copy2(root / "locales.json", tmp / "locales.json")
shutil.copy2(root / "config.default.json", tmp / "config.default.json")

def load(cfg_extra):
    cfg = json.loads((root / "config.default.json").read_text())
    cfg.update(cfg_extra)
    (tmp / "config.json").write_text(json.dumps(cfg, ensure_ascii=False))
    spec = importlib.util.spec_from_file_location("ann", tmp / "bin" / "announce.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

# 1) marker line wins, any shipped marker accepted, length capped
m = load({"lang": "ko", "tone": "3", "max_chars": 50})
got = m.summarize("body\n\n[say] " + "가" * 200)
assert len(got) == 50, got
got = m.summarize("body\n\n[말] 마커 마이그레이션 유지")
assert got.startswith("마커"), got

# 2) fallback: last sentence if question, else first
assert m.summarize("결론입니다. 상세. 커밋할까요?") == "커밋할까요?"
assert m.summarize("결론입니다. 상세1. 상세2.") == "결론입니다."

# 3) legacy tone names alias to levels
m = load({"tone": "friendly"})
assert m._LEVEL == "3", m._LEVEL
m = load({"tone": "playful"})
assert m._LEVEL == "4", m._LEVEL

# 4) level 5 gets the long budget
m = load({"tone": "5"})
assert m.MAX_CHARS > 180

# 5) vendor payload normalization → one shape
m = load({"lang": "ko", "tone": "3"})
r = m.line_for({"prompt_response": "제미나이 응답입니다."})            # Gemini
assert r and r[0] == "done"
r = m.line_for({"event": "afterAgentResponse", "text": "커서 응답."})   # Cursor
assert r and r[0] == "done"
r = m.line_for({"command": "rm -rf x", "cwd": "/p"})                    # Cursor shell
assert r and r[0] == "ask"

# 6) permission speaks the model's own description when present
line = m.permission_line("Bash", {"command": "rm -rf build", "description": "빌드 폴더 삭제"})
assert "빌드 폴더 삭제" in line, line

# 7) muted suppresses everything (module-level check)
m = load({"muted": True})
assert m.CFG.get("muted") is True

# 8) config from before new keys must not crash at import
old = {k: v for k, v in json.loads((root / "config.default.json").read_text()).items()
       if k in ("lang", "tone", "voice", "port", "speed", "steps", "max_chars",
                 "cooldown_sec", "marker", "call_name", "name_chance", "events", "earcons")}
(tmp / "config.json").write_text(json.dumps(old, ensure_ascii=False))
spec = importlib.util.spec_from_file_location("ann2", tmp / "bin" / "announce.py")
m2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m2)
assert m2.line_for({"hook_event_name": "Stop", "last_assistant_message": "[say] ok"})

shutil.rmtree(tmp)
print("announce suite ok")
PY

echo "── wire.py (sandboxed HOME) ────────────"
"$PY" - "$ROOT" <<'PY' && ok "wire preserves foreign hooks, removes cleanly, idempotent" || bad "wire suite"
import json, os, pathlib, subprocess, sys, tempfile

root = pathlib.Path(sys.argv[1])
home = pathlib.Path(tempfile.mkdtemp(prefix="crier-home-"))
env = {**os.environ, "HOME": str(home), "CODEX_HOME": str(home / ".codex")}

def run(*args):
    r = subprocess.run([sys.executable, str(root / "bin" / "wire.py"), *args],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r

# Pre-seed a FOREIGN Stop hook (another tool, e.g. peon-ping)
settings = home / ".claude" / "settings.json"
settings.parent.mkdir(parents=True)
foreign = {"hooks": [{"type": "command", "command": "peon-ping.sh"}]}
settings.write_text(json.dumps({"hooks": {"Stop": [foreign]}}))

run("claude")
cfg = json.loads(settings.read_text())
stops = cfg["hooks"]["Stop"]
cmds = [h["hooks"][0]["command"] for h in stops if "hooks" in h]
assert any("peon-ping" in c for c in cmds), f"foreign Stop hook was clobbered: {cmds}"
assert any("announce.py" in c for c in cmds), f"crier hook missing: {cmds}"

# Idempotent: installing twice must not duplicate
run("claude")
stops = json.loads(settings.read_text())["hooks"]["Stop"]
crier_entries = [h for h in stops if json.dumps(h).find("announce.py") >= 0]
assert len(crier_entries) == 1, f"duplicated on reinstall: {len(crier_entries)}"

# Remove: crier gone, foreign stays
run("claude", "--remove")
cfg = json.loads(settings.read_text())
blob = json.dumps(cfg)
assert "announce.py" not in blob, "crier entries left after remove"
assert "peon-ping" in blob, "foreign hook destroyed by remove"

# All four agents install without error
for a in ("codex", "gemini", "cursor"):
    run(a)
print("wire suite ok")
PY

echo "── prompt.py targets ───────────────────"
"$PY" - "$ROOT" <<'PY' && ok "prompt targets incl. Codex override shadowing" || bad "prompt targets"
import importlib.util, io, contextlib, os, pathlib, sys, tempfile
root = pathlib.Path(sys.argv[1])
home = pathlib.Path(tempfile.mkdtemp(prefix="crier-p-"))
os.environ["CODEX_HOME"] = str(home / ".codex")
spec = importlib.util.spec_from_file_location("p", root / "bin" / "prompt.py")
m = importlib.util.module_from_spec(spec)
with contextlib.redirect_stdout(io.StringIO()):
    spec.loader.exec_module(m)
(home / ".codex").mkdir(parents=True)
assert m.target("codex").name == "AGENTS.md"
(home / ".codex" / "AGENTS.override.md").write_text("x")
assert m.target("codex").name == "AGENTS.override.md", "override must shadow AGENTS.md"
assert m.target("cursor") is None
print("ok")
PY

echo "── setup.py non-interactive ────────────"
"$PY" - "$ROOT" <<'PY' && ok "setup --yes honors flags and locale" || bad "setup non-interactive"
import json, os, pathlib, shutil, subprocess, sys, tempfile
root = pathlib.Path(sys.argv[1])
tmp = pathlib.Path(tempfile.mkdtemp(prefix="crier-s-")); (tmp / "bin").mkdir()
for f in root.glob("bin/*.py"): shutil.copy2(f, tmp / "bin" / f.name)
shutil.copy2(root / "locales.json", tmp / "locales.json")
shutil.copy2(root / "config.default.json", tmp / "config.default.json")
r = subprocess.run([sys.executable, str(tmp / "bin" / "setup.py"),
                    "--agent", "codex", "--lang", "ja", "--name", "Test", "--yes"],
                   capture_output=True, text=True, stdin=subprocess.DEVNULL)
assert r.stdout.strip().splitlines()[-1] == "codex", r.stdout
cfg = json.loads((tmp / "config.json").read_text())
assert cfg["lang"] == "ja" and cfg["call_name"] == "Test"
print("ok")
PY

echo "────────────────────────────────────────"
echo "  passed $PASS · failed $FAIL"
[ "$FAIL" -eq 0 ]
