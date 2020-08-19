# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/shard_util',
    'recipe_engine/properties',
    'recipe_engine/platform',
]


def RunSteps(api):
  builds = api.shard_util.schedule_builds()
  api.shard_util.collect_builds(builds)


def GenTests(api):
  yield api.test(
      'postsubmit', api.properties(subshards=['0', '1_last']),
      api.platform.name('win')
  )
  yield api.test(
      'presubmit',
      api.properties(
          subshards=['0', '1_last'], git_url='https://abc', git_ref='abc'
      ), api.platform.name('linux')
  )
