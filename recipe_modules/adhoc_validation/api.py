# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class AddhocValidationApi(recipe_api.RecipeApi):
  """Wrapper api to run bash scripts as validation in LUCI builder steps.

  This api expects all the bash or bat scripts to exist in its resources
  directory and also expects the validation name to be listed in
  available_validations method.
  """

  def available_validations(self):
    """Returns the list of accepted validations."""
    return ['analyze', 'customer_testing', 'docs', 'fuchsia_precache']

  def run(self, name, validation):
    """Runs a validation as a recipe step.

    Args:
      name(str): The step group name.
      validation(str): The name of a validation to run. This has to correlate
        to a <validation>.sh for linux/mac or <validation>.bat for windows.
    """
    assert (validation in self.available_validations())
    with self.m.step.nest(name):
      resource_name = ''
      if self.m.platform.is_linux:
        resource_name = self.resource('%s.sh' % validation)
        self.m.step('Set execute permission', ['chmod', '755', resource_name])
      if self.m.platform.is_win:
        resource_name = self.resource('%s.bat' % validation)
      self.m.step(validation, [resource_name])
