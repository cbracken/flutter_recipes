# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class JsonUtilApi(recipe_api.RecipeApi):
  """Provides utilities to work with json."""

  def validate_json(self, dev_path, repo):
    """Validates json format for different repos.

    Args:
      dev_path(Path): The path to dev dir of different repos.
      repo(str): The repo name.
    """
    try_json_file = dev_path.join('dev', 'try_builders.json')
    self.m.file.read_json('validate try json format', try_json_file)
    if repo == 'engine' or repo == 'flutter':
      prod_json_file = dev_path.join('dev', 'prod_builders.json')
      self.m.file.read_json('validate prod json format', prod_json_file)
