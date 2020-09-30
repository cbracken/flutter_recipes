#!/bin/bash

# Validate verify binaries are codesigned.

set -e

dart --enable-asserts ./dev/bots/codesign.dart
