# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'depot_tools/git',
    'fuchsia/display_util',
    'fuchsia/upload',
    'recipe_engine/buildbucket',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
    'recipe_engine/swarming',
    'flutter/json_util',
    'repo_util',
    'yaml',
]


# This recipe builds the fuchsia_ctl CIPD package and tests it against the Linux
# Fuchsia builder.
def RunSteps(api):
  packages_dir = api.path['start_dir'].join('packages')
  packages_git_rev = api.repo_util.checkout(
      'packages',
      packages_dir,
      api.properties.get('git_url'),
      api.properties.get('git_ref'),
  )
  # Validates packages builders json format.
  api.json_util.validate_json(packages_dir)

  # Build and uploads a new version of the fuchsia_ctl CIPD package.
  fuchsia_ctl_path = packages_dir.join('packages', 'fuchsia_ctl')
  with api.context(cwd=fuchsia_ctl_path):
    api.step('run tool/build.sh', cmd=['tool/build.sh'])

  cipd_package_name = 'flutter/fuchsia_ctl/${platform}'
  cipd_zip_path = 'fuchsia_ctl.zip'
  api.cipd.build(
      fuchsia_ctl_path.join('build'), cipd_zip_path, cipd_package_name)
  pin = api.cipd.register(cipd_package_name, cipd_zip_path)

  # Test the new fuchsia_ctl CIPD package with a Linux Fuchsia build.
  props = {'fuchsia_ctl_version': pin.instance_id}
  builds = ScheduleBuilds(api, 'Linux Fuchsia', props)
  builds = CollectBuilds(api, builds)
  api.display_util.display_builds(
      step_name='display builds',
      builds=builds.values(),
      raise_on_failure=True,
  )


def ScheduleBuilds(api, builder_name, drone_props):
  req = api.buildbucket.schedule_request(
      swarming_parent_run_id=api.swarming.task_id,
      builder=builder_name,
      properties=drone_props)
  return api.buildbucket.schedule([req])


def CollectBuilds(api, builds):
  return api.buildbucket.collect_builds([build.id for build in builds],
                                        mirror_status=True)


def GenTests(api):
  yield api.test(
      'demo',
      api.properties(
          git_ref='refs/pull/123/head', git_url='https://abc.com/repo'),
  )
