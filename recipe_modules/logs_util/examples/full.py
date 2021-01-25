# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from PB.recipe_modules.recipe_engine.swarming import properties
from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/logs_util',
]


def RunSteps(api):
  env = {}
  api.logs_util.initialize_logs_collection(env)
  api.logs_util.upload_logs('mytaskname')


def GenTests(api):
  yield api.test('basic')
