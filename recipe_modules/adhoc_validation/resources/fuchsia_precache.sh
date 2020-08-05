#!/bin/bash
#
# Validates flutter tool can succesfully download fuchsia
# artifacts.
#
set -e

flutter config --enable-fuchsia
flutter precache --fuchsia --no-android --no-ios --force
flutter precache --flutter_runner --no-android --no-ios --force
