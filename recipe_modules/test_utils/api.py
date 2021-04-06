# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

# The maximum number of lines to be included in the step summary for a failed
# test.
SUMMARY_MAX_LINES = 200

# Default timeout for tests seconds
TIMEOUT_SECS = 3600


class TestUtilsApi(recipe_api.RecipeApi):
  """Utilities to run flutter tests."""

  def is_devicelab_bot(self):
    """Whether the current bot is a devicelab bot or not."""
    return (
        str(self.m.swarming.bot_id).startswith('flutter-devicelab') or
        str(self.m.swarming.bot_id).startswith('flutter-win')
    )

  def run_test(self, step_name, command_list, timeout_secs=TIMEOUT_SECS):
    """Recipe's step wrapper to collect stdout and add it to step_summary.

    Args:
      step_name(str): The name of the step.
      command_list(list(str)): A list of strings with the command and
        parameters to execute.
      timeout_secs(int): The timeout in seconds for this step.
    """
    try:
      self.m.step(
          step_name,
          command_list,
          stdout=self.m.raw_io.output_text(),
          stderr=self.m.raw_io.output_text(),
          timeout=timeout_secs
      )
    except self.m.step.StepFailure as f:
      result = f.result
      # Truncate stdout
      lines = result.stdout.splitlines()
      stdout_lines = lines[-SUMMARY_MAX_LINES:
                          ] if len(lines) > SUMMARY_MAX_LINES else lines
      stdout = '\n'.join(stdout_lines)
      # Truncate stderr
      lines = result.stderr.splitlines()
      stderr_lines = lines[-SUMMARY_MAX_LINES:
                          ] if len(lines) > SUMMARY_MAX_LINES else lines
      stderr = '\n'.join(stderr_lines)
      raise self.m.step.StepFailure('\n\n```%s```\n' % (stdout or stderr))
    finally:
      self.m.step.active_result.presentation.logs[
          'stdout'] = self.m.step.active_result.stdout
      self.m.step.active_result.presentation.logs[
          'stderr'] = self.m.step.active_result.stderr
