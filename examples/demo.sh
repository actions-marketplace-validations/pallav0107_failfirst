#!/usr/bin/env bash
# Self-demo. Usage: FAILFIRST="failfirst" examples/demo.sh   (or FAILFIRST="node js/dist/cli.js")
# Exits non-zero if any expected outcome does not happen.
set -u
export PYTHONDONTWRITEBYTECODE=1  # avoid stale .pyc after a same-size same-second edit
FF="${FAILFIRST:-failfirst}"
W="$(mktemp -d)"
trap 'rm -rf "$W"' EXIT
fail() { echo "DEMO FAILED: $*"; exit 1; }
expect() { local want="$1"; shift; "$@"; local got=$?; [ "$got" -eq "$want" ] || fail "'$*' exit $got, wanted $want"; echo "  -> exit $got (expected)"; }

echo "=== 1. sample repo with a bug ==="
mkdir "$W/repo" && cd "$W/repo"
printf 'def add(a, b):\n    return a - b\n' > calc.py
printf '# Changelog\n' > CHANGELOG.md
cat > failfirst.yaml <<'EOF'
version: 1
criteria:
  - id: add-works
    statement: add(2, 3) returns 5
    check:
      type: command
      cmd: python3 -c "from calc import add; assert add(2, 3) == 5"
  - id: changelog
    statement: the changelog mentions the add fix
    check:
      type: file_contains
      path: CHANGELOG.md
      expect_contains: "fix: add()"
  - id: reads-well
    statement: the fix is minimal and the commit message is clear
    judgment: true
EOF

echo "=== 2. baseline on the UNFIXED code: both machine criteria must fail ==="
expect 0 $FF baseline

echo "=== 3. verify before any fix: not proven ==="
expect 1 $FF verify

echo "=== 4. apply the fix; verify passes (judgment still needs a human) ==="
printf 'def add(a, b):\n    return a + b\n' > calc.py
printf '# Changelog\n- fix: add() subtracted\n' > CHANGELOG.md
expect 3 $FF verify

echo "=== 5. moving the goalposts: weaken a criterion after baseline ==="
sed -i 's/assert add(2, 3) == 5/assert True/' failfirst.yaml
expect 1 $FF verify
$FF verify | grep -q MODIFIED || fail "expected a MODIFIED verdict"

echo "=== 6. a criterion that already passed at baseline is VACUOUS ==="
mkdir "$W/vac" && cd "$W/vac"
printf 'def add(a, b):\n    return a + b\n' > calc.py
cat > failfirst.yaml <<'EOF'
criteria:
  - id: add-works
    statement: add(2, 3) returns 5
    check: { cmd: 'python3 -c "from calc import add; assert add(2, 3) == 5"' }
EOF
expect 1 $FF baseline
$FF verify | grep -q VACUOUS || fail "expected a VACUOUS verdict"
expect 1 $FF verify

echo "=== 7. baseline refuses to overwrite evidence ==="
expect 2 $FF baseline

echo "DEMO OK"
