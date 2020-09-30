# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/adhoc_validation', 'recipe_engine/platform',
    'recipe_engine/properties'
]


def RunSteps(api):
  api.adhoc_validation.run('dart analyze', 'analyze', {}, {})


def GenTests(api):
  yield api.test('win', api.platform.name('win'))
  yield api.test('linux', api.platform.name('linux'))
  yield api.test(
      'mac', api.platform.name('mac'),
      api.properties(dependencies=[{"dependency": "xcode"}])
  )
  yield api.test('mac_nodeps', api.platform.name('mac'))
