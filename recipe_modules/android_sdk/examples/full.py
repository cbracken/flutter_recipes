# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'android_sdk',
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
]


def RunSteps(api):
  env = {}
  env_prefixes = {}
  root = api.path['cache'].join('android29')
  api.android_sdk.install(
      sdk_root=root,
      env=env,
      env_prefixes=env_prefixes
  )
  with api.context(env=env, env_prefixes=env_prefixes):
    api.step('adb devices -l', cmd=['adb', 'devices', '-l'])


def GenTests(api):
  yield (api.test('demo',))
