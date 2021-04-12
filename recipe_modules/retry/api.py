# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class RetryApi(recipe_api.RecipeApi):
  """Utilities to retry recipe steps."""

  def step(
      self,
      step_name,
      cmd,
      max_attempts=3,
      sleep=5.0,
      backoff_factor=1.5,
      **kwargs
  ):
    """Retry the step with exponential backoff.
      Args:
          step_name (str): Name of the step.
          cmd (None|List[int|string|Placeholder|Path]): The program
            arguments to run.
          max_attempts (int): How many times to try before giving up.
          sleep (int or float): The initial time to sleep between attempts.
          backoff_factor (int or float): The factor by which the sleep time
              will be multiplied after each attempt.
    """
    for attempt in range(max_attempts):
      try:
        return self.m.step(step_name, cmd, **kwargs)
      except self.m.step.StepFailure:
        if attempt == max_attempts - 1:
          raise
      self.m.time.sleep(sleep)
      sleep *= backoff_factor
