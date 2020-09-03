#!/bin/bash

# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

export SHARD=tool_coverage
dart --enable-asserts ./dev/bots/test.dart
token=`cat $CODECOV`
bash <(curl -s https://codecov.io/bash) -c -f packages/flutter_tools/coverage/lcov.info -t $token -F flutter_tool
