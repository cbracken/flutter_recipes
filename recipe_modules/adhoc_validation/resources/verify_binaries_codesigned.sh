#!/bin/bash

# Validate verify binaries are codesigned.

set -e

./dev/tools/bin/conductor codesign --verify
