# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'build',
]

def RunSteps(api):
  assert api.build.slave_utils_args

  with api.build.gsutil_py_env():
    api.build.python(
        'runtest',
        api.build.repo_resource('scripts', 'slave', 'runtest.py'),
        args=['--foo', '--bar'])


def GenTests(api):
  yield api.test('basic')
