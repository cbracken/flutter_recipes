# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'flutter/flutter_osx_sdk',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/step',
]

def RunSteps(api):
  with api.flutter_osx_sdk('mac'):
    pass

def GenTests(api):
  yield api.test('basic')
  yield api.test(
    'basic mac',
    api.platform('mac', 64),
  )
  properties_dict = {
    '$depot_tools/osx_sdk': {
      'sdk_version':'deadbeef',
    },
  }
  yield api.test(
    'xcode_version',
    api.platform('mac', 64),
    api.properties(**properties_dict)
  )
  properties_dict = {
    '$depot_tools/osx_sdk': {
      'sdk_version':'deadbeef',
    },
    '$flutter/flutter_osx_sdk': {
      'iphoneos_sdk': '0xDEADBEEF',
    },
  }
  yield api.test(
    'additional deps',
    api.platform('mac', 64),
    api.properties(**properties_dict)
  )
