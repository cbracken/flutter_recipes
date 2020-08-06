# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import (Filter)

DEPS = [
  'json_util',
  'recipe_engine/path',
]

def RunSteps(api):
  api.json_util.validate_json(api.path['cleanup'], 'engine')

def GenTests(api):
  yield api.test('basic')
