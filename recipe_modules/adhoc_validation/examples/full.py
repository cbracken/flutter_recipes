# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/adhoc_validation',
]


def RunSteps(api):
  api.adhoc_validation.run('dart analyze', 'analyze')


def GenTests(api):
  yield api.test('basic')
