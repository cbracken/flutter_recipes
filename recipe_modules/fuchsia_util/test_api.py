# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_test_api
import api


class FuchsiaUtilTestApi(recipe_test_api.RecipeTestApi):

  def run_test_data(self, step_name):
    return self.step_data(step_name, self.m.swarming.trigger(['task1',
                                                              'task2']))

  def device_name_data(self):
    return self.m.swarming.properties(bot_id='abc--fuchsia-node')
