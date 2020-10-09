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
    return [
        'analyze', 'customer_testing', 'docs', 'fuchsia_precache',
        'tool_coverage', 'web_smoke_test', 'verify_binaries_codesigned',
        'build_gallery'
    ]

  def run(self, name, validation, env, env_prefixes, secrets=None):
    """Runs a validation as a recipe step.

    Args:
      name(str): The step group name.
      validation(str): The name of a validation to run. This has to correlate
        to a <validation>.sh for linux/mac or <validation>.bat for windows.
      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
      secrets(dict): The key is the name of the secret and value is the path to kms.
    """
    assert (validation in self.available_validations())
    secrets = secrets or {}
    with self.m.step.nest(name):
      resource_name = ''
      deps = self.m.properties.get('dependencies', [])
      self.m.flutter_deps.required_deps(env, env_prefixes, deps)
      self.m.kms.decrypt_secrets(env, secrets)
      if self.m.platform.is_linux or self.m.platform.is_mac:
        resource_name = self.resource('%s.sh' % validation)
        self.m.step('Set execute permission', ['chmod', '755', resource_name])
      elif self.m.platform.is_win:
        resource_name = self.resource('%s.bat' % validation)
      dep_list = [d['dependency'] for d in deps]
      if 'xcode' in dep_list:
        with self.m.osx_sdk('ios'):
          self.m.flutter_deps.swift()
          checkout_path = self.m.path['start_dir'].join('flutter')
          self.m.flutter_deps.gems(
            env, env_prefixes, checkout_path.join('dev', 'ci', 'mac')
          )
          with self.m.context(env=env, env_prefixes=env_prefixes):
            self.m.step(validation, [resource_name])
      else:
        with self.m.context(env=env, env_prefixes=env_prefixes):
          self.m.step(validation, [resource_name])
