# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'goma',
]


def RunSteps(api):
  jobs = api.goma.recommended_goma_jobs

  # Test caching.
  jobs2 = api.goma.recommended_goma_jobs
  assert jobs == jobs2


def GenTests(api):
  yield api.test('basic')
