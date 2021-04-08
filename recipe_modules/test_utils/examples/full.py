# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from PB.recipe_modules.recipe_engine.swarming import properties
from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/test_utils',
    'recipe_engine/raw_io',
]


def RunSteps(api):
  api.test_utils.run_test('mytest', ['ls', '-la'])
  api.test_utils.is_devicelab_bot()


def GenTests(api):
  yield api.test('passing',)
  yield api.test(
      'failing',
      api.step_data(
          'mytest',
          stdout=api.raw_io.output_text('#failure\nthis is a failure'),
          retcode=1
      )
  )
  very_long_string = "xyz\n" * 1500
  yield api.test(
      'long_stdout',
      api.step_data(
          'mytest',
          stdout=api.raw_io.output_text(very_long_string),
          retcode=1
      )
  )
