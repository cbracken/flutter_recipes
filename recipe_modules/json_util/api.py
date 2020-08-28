# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class JsonUtilApi(recipe_api.RecipeApi):
  """Provides utilities to work with json."""

  def validate_json(self, dev_path):
    """Validates json format for different repos.

    Args:
      dev_path(Path): The path to dev dir of different repos.
    """
    try_json_file = dev_path.join('dev', 'try_builders.json')
    if self.m.path.exists(try_json_file):
      self.m.file.read_json('validate try json format', try_json_file)
    prod_json_file = dev_path.join('dev', 'prod_builders.json')
    if self.m.path.exists(prod_json_file):
      self.m.file.read_json('validate prod json format', prod_json_file)
