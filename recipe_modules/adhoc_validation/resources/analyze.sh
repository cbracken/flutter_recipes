#!/bin/bash
#
# Runs dart analyzer script in the current folder.
set -e
dart --enable-asserts ./dev/bots/analyze.dart
