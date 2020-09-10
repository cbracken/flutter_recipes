# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import (Filter)

DEPS = [
  'json_util',
  'recipe_engine/file',
  'recipe_engine/path',
]

def RunSteps(api):
  api.json_util.validate_json(api.path['cache'])

def GenTests(api):
  yield api.test('try invalid key',
    api.path.exists(api.path['cache'].join(
      'dev', 'try_builders.json')),
    api.step_data('validate luci builder json schemas.validate try json format',
      api.file.read_json({'builders': [{'abc': 'def'}]})),
    api.expect_exception('ValueError')
  )
  yield api.test('try missing key repo',
    api.path.exists(api.path['cache'].join(
      'dev', 'try_builders.json')),
    api.step_data('validate luci builder json schemas.validate try json format',
      api.file.read_json({'builders': [{'name': 'abc'}]})),
    api.expect_exception('ValueError')
  )
  yield api.test('try missing key name',
    api.path.exists(api.path['cache'].join(
      'dev', 'try_builders.json')),
    api.step_data('validate luci builder json schemas.validate try json format',
      api.file.read_json({'builders': [{'repo': 'abc'}]})),
    api.expect_exception('ValueError')
  )
  yield api.test('prod',
    api.path.exists(api.path['cache'].join(
      'dev', 'prod_builders.json')),
    api.step_data('validate luci builder json schemas.validate prod json format',
      api.file.read_json({'builders': [{'repo': 'abc', 'name': 'def'}]}))
  )
