# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DRONE_TIMEOUT_SECS = 3600 * 3  # 3 hours.

from recipe_engine import recipe_api

# Builder names use full platform name instead of short names. We need to
# map short names to full platform names to be able to identify the drone
# used to run the subshards.
PLATFORM_TO_NAME = {'win': 'Windows', 'linux': 'Linux'}


class ShardUtilApi(recipe_api.RecipeApi):
  """Utilities to shard tasks."""

  def schedule_builds(self):
    """Schedules one subbuild per subshard."""
    reqs = []
    for subshard in self.m.properties.get('subshards'):
      task_name = '%s-%s' % (self.m.properties.get('shard', ''), subshard)
      drone_props = {
          'subshard':
              subshard, 'shard':
                  self.m.properties.get('shard', ''), 'android_sdk_license':
                      self.m.properties.get('android_sdk_license', ''),
          'android_sdk_preview_license':
              self.m.properties.get('android_sdk_preview_license', ''),
          'dependencies':
              list(self.m.properties.get('dependencies', [])), 'task_name':
                  task_name
      }
      if self.m.properties.get('git_url'):
        drone_props['git_url'] = self.m.properties.get('git_url')
      if self.m.properties.get('git_ref'):
        drone_props['git_ref'] = self.m.properties.get('git_ref')
      platform_name = PLATFORM_TO_NAME.get(self.m.platform.name)
      req = self.m.buildbucket.schedule_request(
          swarming_parent_run_id=self.m.swarming.task_id,
          builder='%s SDK Drone' % platform_name,
          properties=drone_props,
          # Having main build and subbuilds with the same priority can lead
          # to a deadlock situation when there are limited resources. For example
          # if we have only 7 mac bots and we get more than 7 new build requests the
          # within minutes of each other then the 7 bots will be used by main tasks
          # and they will all timeout waiting for resources to run subbuilds.
          # Increasing priority won't fix the problem but will make the deadlock
          # situation less unlikely.
          # https://github.com/flutter/flutter/issues/59169.
          priority=25
      )
      reqs.append(req)
    return self.m.buildbucket.schedule(reqs)

  def collect_builds(self, builds):
    """Waits for a list of builds to complete.

    Args:
      builds(list(buildbucket.Build))
    """
    step = self.m.step('Task Shards', None)
    for build in builds:
      task_name = build.input.properties.fields['task_name'].string_value
      step.presentation.links[task_name] = self.m.buildbucket.build_url(
          build_id=build.id
      )
    return self.m.buildbucket.collect_builds([build.id for build in builds],
                                             timeout=DRONE_TIMEOUT_SECS,
                                             mirror_status=True)
