# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import (Filter)

DEPS = [
    'kms',
    'recipe_engine/path',
    'recipe_engine/platform',
]


def RunSteps(api):
  env = {}
  api.kms.decrypt_secrets(env, {'a': 'a'})
  api.kms.get_secret('in', api.path['cleanup'].join('out'))


def GenTests(api):
  yield api.test('basic')
  yield api.test(
      'win',
      api.platform('win', 64),
      api.post_process(Filter('cloudkms get key')),
  )
