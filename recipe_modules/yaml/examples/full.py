# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'yaml',
    'recipe_engine/json',
    'recipe_engine/assertions',
    'recipe_engine/file',
    'recipe_engine/raw_io',
]

YAML_CONTENT = """
tasks:
  - task: one
    script: myscript
"""


def RunSteps(api):
  result = api.yaml.read('yaml', api.resource('sample.yaml'), api.json.output())
  api.assertions.assertEqual(result.json.output, {'key': 'value'})


def GenTests(api):
  yield (
      api.test('passing') +
      api.step_data('yaml.parse', api.json.output({'key': 'value'})) +
      api.step_data('yaml.read',
                    api.file.read_text(text_content=YAML_CONTENT)))
  yield (
      api.test('fail_to_read') +
      api.step_data('yaml.read', retcode=1, stderr=api.raw_io.output('fail')))
