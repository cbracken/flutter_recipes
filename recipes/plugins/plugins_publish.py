# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'recipe_engine/step',
]

def RunSteps(api):
    """Recipe to run flutter plugin publish."""
    # For now we only echo to test if this recipe runs.
    api.step('report', ['echo', 'Complete publishing plugins (tests)]'])

def GenTests(api):
  yield api.test('basic')