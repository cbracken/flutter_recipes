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
    with self.m.step.nest('validate luci builder json schemas'):
      try_json_file = dev_path.join('dev', 'try_builders.json')
      if self.m.path.exists(try_json_file):
        try_json_data = self.m.file.read_json(
            'validate try json format', try_json_file
        )
        self.validate_builder_schema('try', try_json_data)
      prod_json_file = dev_path.join('dev', 'prod_builders.json')
      if self.m.path.exists(prod_json_file):
        prod_json_data = self.m.file.read_json(
            'validate prod json format', prod_json_file
        )
        self.validate_builder_schema('prod', prod_json_data)

  def validate_builder_schema(self, bucket, json_data):
    """Validates the schema of a list of builder configs.

    Args:
      bucket(str): the bucket of builders, with possible values: "try" and "prod".
      json_data(dict): a list of builder configs in json format.
      Try builders example:
        {
          "builders": [
            {
              "name": "abc",
              "repo": "def",
              "task_name": "ghi",
              "enabled":true,
              "run_if":["dev/", "packages/flutter_tools/", "bin/"]
            }
          ]
        }
      Prod builders example:
        {
          "builders": [
            {
              "name": "abc",
              "repo": "def",
              "task_name": "ghi",
              "flaky":true,
            }
          ]
        }
    """
    supported_builder_keys = {
        'try': ['repo', 'name', 'enabled', 'run_if', 'task_name'],
        'prod': ['repo', 'name', 'task_name', 'flaky']
    }

    builders = json_data['builders']
    with self.m.step.nest('validate %s builders' % bucket):
      for builder in builders:
        builder_keys_flag = {
            key: False for key in supported_builder_keys[bucket]
        }
        for key in builder.keys():
          if key not in supported_builder_keys[bucket]:
            raise ValueError(
                'Unsupported key: %s in builder: %s' %
                (key, self.m.json.dumps(builder))
            )
          builder_keys_flag[key] = True
        if not builder_keys_flag['repo']:
          raise ValueError(
              'Missing key: repo in builder: %s' % self.m.json.dumps(builder)
          )
        if not builder_keys_flag['name']:
          raise ValueError(
              'Missing key: name in builder: %s' % self.m.json.dumps(builder)
          )
