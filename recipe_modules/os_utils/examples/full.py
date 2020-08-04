# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/os_utils',
    'recipe_engine/platform',
]


def RunSteps(api):
  api.os_utils.kill_win_processes()


def GenTests(api):
  yield api.test(
      'basic',
      api.platform('win', 64),
  )
