# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.post_process import DoesNotRun, Filter, StatusFailure

DEPS = [
    'flutter/repo_util',
    'recipe_engine/path',
]


def RunSteps(api):
  api.repo_util.checkout('unsupported_repo',
                         api.path['start_dir'].join('unsupported_repo'))


def GenTests(api):
  yield api.test(
      'unsupported',
      api.expect_exception('ValueError'),
  )
