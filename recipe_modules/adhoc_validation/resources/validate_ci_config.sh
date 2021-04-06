#!/usr/bin/env bash

set -e

FLUTTER_PATH="$PWD"

if [ -z "$COCOON_PATH" ] || [ ! -d "$COCOON_PATH" ]; then
  echo "Cocoon needs to be cloned and its path provided via the env variable"
  echo 'COCOON_PATH.'
  exit 1
fi

# Add flutter bin to path
export PATH="$FLUTTER_PATH/bin:$PATH"
cd $COCOON_PATH
./test_utilities/bin/config_test_runner.sh "$FLUTTER_PATH/.ci.yaml"
