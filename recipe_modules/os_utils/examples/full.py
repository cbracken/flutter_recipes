# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/os_utils',
    'recipe_engine/platform',
    'recipe_engine/python',
]


def RunSteps(api):
  api.os_utils.kill_win_processes()

  with api.os_utils.make_temp_directory('Create temp directory') as temp_dir:
    file = temp_dir.join('artifacts.zip')


def GenTests(api):
  yield api.test(
      'basic',
      api.platform('win', 64),
  )
  yield api.test(
      'with_failures', api.platform('win', 64),
      api.step_data("Killing Windows Processes.stop dart", retcode=1))
