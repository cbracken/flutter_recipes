# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'android_sdk',
    'recipe_engine/properties',
    'recipe_engine/step',
]


def RunSteps(api):
  api.android_sdk.install()
  with api.android_sdk.context():
    api.step('adb devices -l', cmd=['adb', 'devices', '-l'])


def GenTests(api):
  yield (api.test(
      'demo',
      api.properties(
          android_sdk_license='android_sdk_hash',
          android_sdk_preview_license='android_sdk_preview_hash',
      ),
  ))
