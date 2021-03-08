# Copyright 2020 The Fuchsia Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    "flutter/display_util",
    "fuchsia/status_check",
    "recipe_engine/file",
    "recipe_engine/path",
    "recipe_engine/swarming",
]


def RunSteps(api):
  request = (
      api.swarming.task_request().with_name("flutter_fuchsia_unittests"
                                           ).with_priority(100)
  )
  request = request.with_slice(
      0,
      request[0].with_command(
          ["./run_tests.sh", "image_name", "packages_name"]
      ).with_dimensions(
          pool="luci.flutter.tests"
      ).with_isolated("isolated_hash").with_expiration_secs(3600)
      .with_io_timeout_secs(3600).with_execution_timeout_secs(3600)
      .with_idempotent(True).with_containment_type("AUTO"),
  )
  # Trigger the task request.
  metadata = api.swarming.trigger("Trigger Tests", requests=[request])
  links = {m.id: m.task_ui_link for m in metadata}
  # Collect the result of the task by metadata.
  fuchsia_output = api.path["cleanup"].join("fuchsia_test_output")
  api.file.ensure_directory("swarming output", fuchsia_output)
  results = api.swarming.collect(
      "collect", metadata, output_dir=fuchsia_output, timeout="30m"
  )
  api.display_util.display_tasks(
      step_name="display tasks",
      results=results,
      metadata=metadata,
      raise_on_failure=True,
  )


def GenTests(api):
  yield (
      api.status_check.test("Test_Infra_Failure", status="infra_failure") +
      api.step_data(
          "Trigger Tests", api.swarming.trigger(["task1", "task2"],
                                                initial_id=0)
      ) + api.step_data(
          "collect",
          api.swarming.collect([
              api.swarming.task_result(
                  id="0", name="task1", state=api.swarming.TaskState.KILLED
              ),
              api.swarming.task_result(id="1", name="task2", failure=True),
          ]),
      )
  )
  yield (
      api.status_check.test("Test_Failure", status="failure") + api.step_data(
          "Trigger Tests", api.swarming.trigger(["task1", "task2"],
                                                initial_id=0)
      ) + api.step_data(
          "collect",
          api.swarming.collect([
              api.swarming.task_result(id="0", name="task1"),
              api.swarming.task_result(id="1", name="task2", failure=True),
          ]),
      )
  )
  yield (
      api.status_check.test("Test_Success", status="success") + api.step_data(
          "Trigger Tests", api.swarming.trigger(["task1"], initial_id=0)
      ) + api.step_data(
          "collect",
          api.swarming.collect([
              api.swarming.task_result(id="0", name="task1"),
          ]),
      )
  )
