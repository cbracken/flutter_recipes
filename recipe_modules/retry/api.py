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

    Returns a `step_data.StepData` for the running step.
    """
    for attempt in range(max_attempts):
      step = self.m.step(step_name, cmd, ok_ret='any', **kwargs)
      if step.retcode != 0:
        if attempt == max_attempts - 1:
          step.presentation.status = self.m.step.FAILURE
          raise self.m.step.StepFailure('.'.join(step.name_tokens), step)
        self.m.time.sleep(sleep)
        sleep *= backoff_factor
      else:
        return step


  def wrap(
      self,
      func,
      max_attempts=3,
      sleep=5.0,
      backoff_factor=1.5,
      retriable_codes='any',
      **kwargs
  ):
    """Retry wrapped function with exponential backoff.
    Args:
        step_name (str): Name of the step.
        func (callable): A function that performs the action that should be
          retried on failure. If it raises a `StepFailure`, it will be retried.
          Any other exception will end the retry loop and bubble up.
        retriable_codes ('any' or Tuple(int)): Return codes that should allow a
          retry. Pass 'any' to accept any.
        max_attempts (int): How many times to try before giving up.
        sleep (int or float): The initial time to sleep between attempts.
        backoff_factor (int or float): The factor by which the sleep time
            will be multiplied after each attempt.
    """
    for attempt in range(max_attempts):
      try:
        return func()
      except self.m.step.StepFailure:
        step = self.m.step.active_result
        retriable_failure = retriable_codes == 'any' or \
            step.retcode in retriable_codes
        if not retriable_failure or attempt == max_attempts - 1:
            raise
        self.m.time.sleep(sleep)
        sleep *= backoff_factor
