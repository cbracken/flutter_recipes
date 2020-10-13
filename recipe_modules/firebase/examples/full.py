# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'flutter/firebase',
    'recipe_engine/path',
]


def RunSteps(api):
  docs_path = api.path['start_dir'].join('flutter', 'dev', 'docs')
  api.firebase.deploy_docs({}, {}, docs_path, 'myproject')


def GenTests(api):
  yield api.test('basic')
