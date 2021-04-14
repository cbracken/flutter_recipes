#!/bin/bash

# Helper script to unlock the keychain in the same session
# as the test runner script.
set -e

if [ -f /usr/local/bin/unlock_login_keychain.sh ]
then
  /usr/local/bin/unlock_login_keychain.sh
else
  echo "This bot does not support codesigning"
fi

args=( "$@" )
dart bin/test_runner.dart test "${args[@]}"
