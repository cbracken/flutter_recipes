# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.protobuf import json_format
from PB.go.chromium.org.luci.led.job import job as job_pb2
from recipe_engine import recipe_test_api


class JobTestApi(recipe_test_api.RecipeTestApi):

  def mock_launch(self, buildbucket_build=None, task_id="job_task_id"):
    """Returns mock data for the launch function.

    Args:
      buildbucket_build (TestData): Emulates a buildbucket build. It is usually
          an output from api.buildbucket.x_build().
      task_id (str): Id of the swarming task.
    """
    ret = self.empty_test_data()

    # Attaches current build.
    if not buildbucket_build:
      buildbucket_build = self.m.buildbucket.ci_build(
          project="flutter", bucket="try", builder="Linux")
    ret += buildbucket_build

    # Attaches task_id of the launched swarming task.
    # led launch mock will take ....infra.swarming.task_id as this build's
    # launched swarming ID.
    jd = job_pb2.Definition()
    jd.buildbucket.bbagent_args.build.infra.swarming.task_id = task_id
    ret += self.m.led.mock_get_builder(jd)
    return ret

  def mock_collect(self,
                   task_ids,
                   presentation_step_name,
                   swarming_results=None,
                   build_protos=None):
    """Returns mock data for the collect function.

    Args:
      task_ids (list(str)): List of swarming task ids.
      presentation_step_name (str): The step name of the presentation.
      swarming_results (list(dict)): List of the outputs from
          api.swarming.task_result() in the order of task_ids.
      build_protos (list(build_pb2.Build)): List of build proto messages in the
          order of task_ids.
    """
    ret = self.empty_test_data()

    # Attaches swarming results.
    if not swarming_results:
      swarming_results = [
          self.m.swarming.task_result(id=task_id, name="my_task_%d" % i)
          for i, task_id in enumerate(task_ids)
      ]

    ret += self.step_data(
        "%s.collect" % presentation_step_name,
        self.m.swarming.collect(swarming_results),
    )

    # Attaches build protos.
    if not build_protos:
      build_protos = [
          self.m.buildbucket.ci_build_message(build_id=1000 + i)
          for i, _ in enumerate(task_ids)
      ]

    for i, id in enumerate(task_ids):
      # Mocks read build.proto.json.
      step_name = "%s.read build.proto.json" % presentation_step_name
      if i > 0:
        step_name += " (%d)" % (i + 1)
      ret += self.step_data(
          step_name,
          self.m.file.read_text(json_format.MessageToJson(build_protos[i])),
      )

    return ret
