# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'depot_tools/gsutil',
    'flutter/web_util',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/runtime',
    'recipe_engine/step',
]


def RunSteps(api):
  engine_checkout_path = api.path['cache'].join('builder', 'src')
  api.web_util.prepare_dependencies(engine_checkout_path)
  api.web_util.upload_failing_goldens(engine_checkout_path, 'chrome')

def GenTests(api):
  golden_yaml_file = {'repository': 'repo', 'revision': 'b6efc758'}
  browser_yaml_file = {
      'required_driver_version': {
          'chrome': 84
      },
      'chrome': {
          'Linux': '768968',
          'Mac': '768985',
          'Win': '768975'
      }
  }
  yield api.test(
      'fail case',
      api.expect_exception('ValueError'),
      api.properties(
          dependencies=['invalid_dependency'],), api.platform(
              'linux', 64)) + api.platform.name('linux')
  yield api.test(
      'clone repo',
      api.step_data('read yaml.parse', api.json.output(golden_yaml_file)),
      api.properties(
          gcs_goldens_bucket='mybucket',
          dependencies=['goldens_repo'],), api.platform(
              'linux', 64)) + api.platform.name('linux') + api.runtime(is_experimental=False)
  yield api.test(
      'chrome driver',
      api.step_data('read browser lock yaml.parse',
                    api.json.output(browser_yaml_file)),
      api.properties(
          dependencies=['chrome_driver'],), api.platform(
              'linux', 64)) + api.platform.name('linux')
  yield api.test(
      'firefox driver',
      api.properties(
          dependencies=['firefox_driver'],), api.platform(
              'linux', 64)) + api.platform.name('linux')
  yield api.test(
      'chrome',
      api.step_data('read browser lock yaml.parse',
                    api.json.output(browser_yaml_file)),
      api.properties(
          dependencies=['chrome'],), api.platform(
              'linux', 64)) + api.platform.name('linux')
  yield api.test(
      'mac-post-submit',
      api.step_data('read yaml.parse', api.json.output(golden_yaml_file)),
      api.properties(
          goma_jobs='200',
          gcs_goldens_bucket='mybucket',
          dependencies=['goldens_repo'],
          command_args=['test', '--browser=ios-safari', '--unit-tests-only'],
          command_name='ios-safari-unit-tests'), api.platform(
              'mac', 64)) + api.runtime(is_experimental=False)
