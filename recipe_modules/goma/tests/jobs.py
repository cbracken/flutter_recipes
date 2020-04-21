# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'goma',
  'recipe_engine/platform',
]


def RunSteps(api):
  jobs = api.goma.jobs
  assert jobs in (api.platform.cpu_count * 10, 99)


def GenTests(api):
  yield api.test(
      'default-is-recommended-50',
      api.platform.name('linux'),
  )
  yield api.test(
      'can-be-overridden-99',
      api.goma(jobs=99),
  )
