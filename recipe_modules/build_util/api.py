# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class BuildUtilApi(recipe_api.RecipeApi):
  """Gn and Ninja wrapper functions."""

  def run_gn(self, gn_args, checkout_path):
    """Run a gn command with the given arguments.

    Args:
      gn_args(list): A list of strings to be passed to the gn command.
      checkout_path(Path): A path object with the checkout location.
    """
    gn_cmd = ['python', checkout_path.join('flutter/tools/gn'), '--goma']
    if self.m.properties.get('no_lto', False) and '--no-lto' not in gn_args:
      gn_args += ('--no-lto',)
    gn_cmd.extend(gn_args)
    self.m.step('gn %s' % ' '.join(gn_args), gn_cmd)

  def build(self, config, checkout_path, targets):
    """Builds using ninja.

    Args:
      config(str): A string with the configuration to build.
      checkout_path(Path): A path object with the checkout location.
      targets(list): A list of string with the ninja targets to build.
    """
    build_dir = checkout_path.join('out/%s' % config)
    goma_jobs = self.m.properties['goma_jobs']
    ninja_args = [
        self.m.depot_tools.ninja_path, '-j', goma_jobs, '-C', build_dir
    ]
    ninja_args.extend(targets)
    self.m.goma.ensure()
    with self.m.goma.build_with_goma(), self.m.depot_tools.on_path():
      name = 'build %s' % ' '.join([config] + list(targets))
      self.m.step(name, ninja_args)
