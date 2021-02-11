# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'devicelab_osx_sdk',
  'recipe_engine/platform',
  'recipe_engine/properties',
  'recipe_engine/step',
]


def RunSteps(api):
  with api.devicelab_osx_sdk('mac'):
    api.step('gn', ['gn', 'gen', 'out/Release'])
    api.step('ninja', ['ninja', '-C', 'out/Release'])


def GenTests(api):
  for platform in ('linux', 'mac', 'win'):
    yield (api.test(platform) +
           api.platform.name(platform) +
           api.properties(**{'$flutter/devicelab_osx_sdk': {
              'sdk_version': 'deadbeef',
           }}))

  yield api.test(
      'explicit_version',
      api.platform.name('mac'),
      api.properties(**{'$flutter/devicelab_osx_sdk': {
        'sdk_version': 'deadbeef',
      }})
  )
