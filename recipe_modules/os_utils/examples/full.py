# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from PB.recipe_modules.recipe_engine.swarming import properties
from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/os_utils',
    'recipe_engine/platform',
    'recipe_engine/python',
    'recipe_engine/properties',
]


def RunSteps(api):
  api.os_utils.kill_processes()
  api.os_utils.collect_os_info()

  with api.os_utils.make_temp_directory('Create temp directory') as temp_dir:
    file = temp_dir.join('artifacts.zip')
  api.os_utils.clean_derived_data()
  api.os_utils.shutdown_simulators()


def GenTests(api):
  yield api.test(
      'basic',
      api.platform('win', 64),
  )
  yield api.test(
      'mac_linux',
      api.platform('mac', 64),
  )
  yield api.test(
      'linux_linux',
      api.platform('linux', 64),
  )
  yield api.test(
      'with_failures', api.platform('win', 64),
      api.step_data("Killing Processes.stop dart", retcode=1)
  )
  yield api.test(
      'clean_derived_data', api.platform('mac', 64),
      api.properties.environ(
          properties.EnvProperties(SWARMING_BOT_ID='flutter-devicelab-mac-1')
      )
  )
