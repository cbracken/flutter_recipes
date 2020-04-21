# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'goma',
  'recipe_engine/buildbucket',
  'recipe_engine/properties',
  'recipe_engine/runtime',
]


def RunSteps(api):
  api.goma.ensure_goma(client_type='candidate')
  api.goma.start()
  api.goma.stop(build_exit_status=0)


def GenTests(api):
  yield api.test(
      'basic',
      api.buildbucket.ci_build(builder='test_buildername'),
  )

  yield api.test(
      'luci_and_experimental',
      api.runtime(is_luci=True, is_experimental=True),
      api.buildbucket.ci_build(builder='test_buildername'),
  )
