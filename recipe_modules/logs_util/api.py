# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class LogUtilsApi(recipe_api.RecipeApi):
  """Utilities to collect logs in a generic way."""

  def initialize_logs_collection(self, env):
    """Initializes log processing.

    The initialization process creates a temp directory and adds it to the
    FLUTTER_LOGS_DIR env variable to make it available to the task steps. Task
    steps can place any files they want to upload to GCS as public logs.

    Args:
      env(dict): Env variables dictionary.
    """
    # Create a temp folder to keep logs until we can upload them to gcs
    # at the end of the execution of the test.
    with self.m.step.nest('Initialize logs'):
      logs_path = self.m.path['cleanup'].join('flutter_logs_dir')
      self.m.file.ensure_directory('Ensure %s' % logs_path, logs_path)
      env['FLUTTER_LOGS_DIR'] = logs_path

  def upload_logs(self):
    """Upload the log files in FLUTTER_LOGS_DIR to GCS."""
    with self.m.step.nest('Process logs'):
      self.m.bucket_util.upload_folder(
          'Upload logs',
          str(self.m.path['cleanup']),
          'flutter_logs_dir',
          'flutter_logs.zip',
          bucket_name='flutter_logs',
      )
