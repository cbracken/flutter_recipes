# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    "flutter/job",
    "recipe_engine/properties",
    "recipe_engine/step",
    "recipe_engine/swarming",
]

PROPERTIES = {
    "test_name": Property(kind=str, help="Name of the test"),
}


def RunSteps(api, test_name):
  job0 = api.job.new("fake_job0")
  job0.properties.update({
      "recipe": "fake_recipe",
      "foo": ["a", "b"],
  })
  job0.dimensions.update({
      "id": "fake_bot_id",
      "pool": "luci.flutter.staging",
  })

  job1 = api.job.new("fake_job1")

  if test_name == "launch":
    with api.step.nest("launch job") as presentation:
      job0 = api.job.launch(job0, presentation)
  elif test_name == "collect":
    job0.task_id = "task_id0"
    job1.task_id = "task_id1"
    with api.step.nest("collect builds") as presentation:
      api.job.collect([job0, job1], presentation)
  elif test_name == "current_recipe":
    api.job.current_recipe()


def GenTests(api):
  yield api.test(
      "launch",
      api.properties(test_name="launch"),
      api.job.mock_launch(),
  )
  yield api.test(
      "collect",
      api.properties(test_name="collect"),
      api.job.mock_collect(["task_id0", "task_id1"], "collect builds"),
  )
  yield api.test(
      "collect_failed_states",
      api.properties(test_name="collect"),
      api.job.mock_collect(
          ["task_id0", "task_id1"],
          "collect builds",
          swarming_results=[
              api.swarming.task_result(
                  id="task_id0", name="my_task_0", state=None),
              api.swarming.task_result(
                  id="task_id1",
                  name="my_task_1",
                  state=api.swarming.TaskState.TIMED_OUT),
          ],
      ),
  )
  yield api.test(
      "current_recipe",
      api.properties(test_name="current_recipe"),
  )
