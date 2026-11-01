#!/usr/bin/env bash
# Verifies the spec-first rule (constitution principle II): specs/001-docs-studio/spec.md must have
# been committed in an earlier commit than the first commit that adds any file under backend/ or
# frontend/ (their CLAUDE.md files are exempt).
#
# Exit codes: 0 = the rule holds (or nothing has been implemented yet), 1 = the rule is broken,
# 2 = it cannot be checked (not a git repository, or no commits).
set -euo pipefail

SPEC="specs/001-docs-studio/spec.md"

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  echo "check-spec-first: this is not a git repository" >&2
  exit 2
fi
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  echo "check-spec-first: there are no commits yet, so the order cannot be checked" >&2
  exit 2
fi

# One line per added file, grouped under a "commit <hash>" line, oldest commit first.
history=$(git log --reverse --diff-filter=A --name-only --format='commit %h' -- \
  "$SPEC" backend frontend ':(exclude)backend/CLAUDE.md' ':(exclude)frontend/CLAUDE.md')

result=$(printf '%s\n' "$history" | awk -v spec="$SPEC" '
  /^commit / { n++; hash=$2; next }
  NF == 0    { next }
  $0 == spec { if (spec_n == 0) { spec_n = n; spec_hash = hash } ; next }
  { if (impl_n == 0) { impl_n = n; impl_hash = hash; impl_file = $0 } }
  END {
    if (spec_n == 0)            { print "MISSING"; exit }
    if (impl_n == 0)            { print "NOIMPL " spec_hash; exit }
    if (spec_n < impl_n)        { print "OK " spec_hash " " impl_hash " " impl_file; exit }
    print "BROKEN " spec_hash " " impl_hash " " impl_file
  }')

case "$result" in
  MISSING*)
    echo "check-spec-first: FAIL: $SPEC has not been committed" >&2
    exit 1
    ;;
  NOIMPL*)
    echo "check-spec-first: OK: $SPEC is committed (${result#NOIMPL }) and nothing under backend/ or frontend/ has been committed yet"
    ;;
  OK*)
    set -- $result
    echo "check-spec-first: OK: $SPEC was committed in $2, before the first implementation file ($4) in $3"
    ;;
  BROKEN*)
    set -- $result
    echo "check-spec-first: FAIL: the implementation file $4 was committed in $3, which is not after $SPEC ($2)" >&2
    exit 1
    ;;
  *)
    echo "check-spec-first: unexpected result: $result" >&2
    exit 2
    ;;
esac
