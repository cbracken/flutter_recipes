# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/flutter_deps',
    'recipe_engine/path',
    'recipe_engine/assertions',
]


def RunSteps(api):
  env = {}
  env_prefixes = {}
  api.flutter_deps.open_jdk(env, env_prefixes)
  api.assertions.assertTrue(env.get('JAVA_HOME'))
  api.assertions.assertEqual(
      env_prefixes.get('PATH'), [api.path['cache'].join('java', 'bin')])
  env_prefixes = {}
  env = {}
  api.flutter_deps.chrome_and_driver(env, env_prefixes)
  api.assertions.assertTrue(env.get('CHROME_NO_SANDBOX'))
  api.assertions.assertTrue(env.get('CHROME_EXECUTABLE'))
  api.assertions.assertEqual(
      env_prefixes.get('PATH'), [
          api.path['cache'].join('chrome', 'chrome'), api.path['cache'].join(
              'chrome', 'drivers')
      ])


def GenTests(api):
  yield api.test('basic')
