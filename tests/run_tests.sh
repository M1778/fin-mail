#!/bin/sh
# Runs the fin-mail test suite: unit tests + live SMTP verification.
# Usage (from the fin-mail repo root):
#   sh tests/run_tests.sh
# Uses $FINC, else `finc` on PATH, else this sandbox's binary.
set -e
if [ -z "$FINC" ]; then
  if command -v finc > /dev/null 2>&1; then
    FINC="finc"
  else
    FINC="$HOME/workspace/fin-dev/tester-1/Fin/build/finc"
  fi
fi
cd "$(dirname "$0")/.."
"$FINC" -I src tests/test_mail.fin -o test_mail
./test_mail
FINC="$FINC" python3 tests/live_smtp.py
