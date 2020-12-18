# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/step',
    'recipe_engine/time',
    'flutter/json_util',
    'repo_util',
]

# This recipe builds the device_doctor CIPD package.
def RunSteps(api):
  cocoon_dir = api.path['start_dir'].join('cocoon')
  cocoon_git_rev = api.repo_util.checkout(
      'cocoon',
      cocoon_dir,
      api.properties.get('git_url'),
      api.properties.get('git_ref'),
  )
  # Validates cocoon builders json format.
  api.json_util.validate_json(cocoon_dir)

  # Builds and uploads a new version of the device_doctor CIPD package.
  device_doctor_path = cocoon_dir.join('device_doctor')
  with api.context(cwd=device_doctor_path):
    if api.platform.is_linux or api.platform.is_mac:
      build_file = device_doctor_path.join('tool', 'build.sh')
      api.step('build package', cmd=['bash', build_file])
    else:
      build_file = device_doctor_path.join('tool', 'build.bat')
      api.step('build package', cmd=[build_file])

  cipd_package_name = 'flutter/device_doctor/${platform}'
  cipd_zip_path = 'device_doctor.zip'

  api.cipd.build(
      device_doctor_path.join('build'), cipd_zip_path, cipd_package_name)
  time = str(int(api.time.time()))
  api.cipd.register(cipd_package_name, cipd_zip_path, refs=['staging'],
      tags={'sha_timestamp': cocoon_git_rev+'_'+time})


def GenTests(api):
  for platform in ('mac', 'linux', 'win'):
    yield api.test(
        platform,
        api.properties(
            git_ref='refs/pull/123/head', git_url='https://abc.com/repo'),
        api.platform(platform, 64)
    )
