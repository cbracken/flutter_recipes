# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class YamlApi(recipe_api.RecipeApi):
  """Provides utilities to parse yaml files."""

  def read(self, step_name, file_path, json_place_holder):
    """Reads a yaml file.

    It currently shells out to a script which converts the yaml to json,
    this way it can use vpython to import pyyaml. To achieve the same
    from the recipe we need to specify pyyaml at the root file. Please
    change this behavior to be inline if it becomes easier to specify
    vpython packages dependencies in a recipe module.

    Args:
      step_name: (str) the name of the step for reading the yaml.
      file_path: (str) the path to the yaml file.
      json_place_holder: (JsonOutputPlaceholder) for the parsed yaml content.
    Returns:
      StepData with the result from the step.
    """
    with self.m.step.nest(step_name) as presentation:
      content = self.m.file.read_text('read', file_path)
      presentation.logs['yaml'] = content
      return self.m.python(
          'parse', self.resource('parse_yaml.py'),
          args=['--yaml_file', file_path, '--json_file', self.m.json.output()],
          venv=True)
