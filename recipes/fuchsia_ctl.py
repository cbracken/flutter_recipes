# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'depot_tools/git',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
    'recipe_engine/file',
    'recipe_engine/swarming',
    'fuchsia/buildbucket_util',
    'fuchsia/upload',
    'recipe_engine/cipd',
    'yaml',
]


# This recipe builds the fuchsia_ctl CIPD package and tests it against the Linux
# Fuchsia builder.
def RunSteps(api):
  # Checkout the flutter/packages repository.
  packages_git_url = 'https://github.com/flutter/packages/'
  if 'git_url' in api.properties:
    packages_git_url = api.properties['git_url']

  packages_git_ref = 'master'
  if 'git_ref' in api.properties:
    packages_git_ref = api.properties['git_ref']

  packages_git_hash = api.git.checkout(
      packages_git_url,
      ref=packages_git_ref,
      recursive=True,
      set_got_revision=True,
      tags=True)

  # Build and uploads a new version of the fuchsia_ctl CIPD package.
  fuchsia_ctl_path = api.path['start_dir'].join('packages', 'fuchsia_ctl')
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
  api.buildbucket_util.display_builds(
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
