# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from google.protobuf import json_format
from recipe_engine import recipe_api
from PB.go.chromium.org.luci.buildbucket.proto import build as build_pb2


class Job(object):
  """Describes a job that could be launched via led.

  Attributes:
    name (str): Name of the job.
    properties (dict): Properties as the arguments to `led edit -p`.
    dimensions (dict): Dimensions as the arguments to `led edit -d`.
    task_id (str): Id of the swarming task.
    task_server (str): Host name of the swarming server, e.g.
        "chromium-swarm.appspot.com".
    task_result (api.swarming.TaskResult): Result of the swarming task.
    build_proto(build_pb2.Build): Proto generated from a buildbucket build.
    outcome (str): The outcome could be "success", "none" when task_result.state
        is None, or TaskState in lower case.
  """

  def __init__(self, name):
    # Metadata attached before execution.
    assert isinstance(name, basestring)
    self.name = name
    self.properties = {'name': name}
    self.dimensions = {}

    # Metadata attached during execution.
    self.task_id = None
    self.task_server = None

    # Metadata attached after execution.
    self.task_result = None
    self.build_proto = None
    self.outcome = None

  @property
  def task_url(self):
    """Returns the URL of the associated task in the Swarming UI."""
    return "%s/task?id=%s" % (self.task_server, self.task_id)

  @property
  def milo_url(self):
    """Returns the URL of the associated task in the Milo UI."""
    return "https://ci.chromium.org/swarming/task/%s?server=%s" % (
        self.task_id, self.task_server)


class JobApi(recipe_api.RecipeApi):
  """API for launching jobs and collecting the results."""

  def __init__(self, *args, **kwargs):
    super(JobApi, self).__init__(*args, **kwargs)

  def new(self, job_name):
    return Job(job_name)

  def current_recipe(self):
    return self.m.properties.get('recipe')

  def launch(self, job, presentation):
    """Launches a job with led.

    Args:
      job (Job): The job definition.
      presentation (StepPresentation): The presentation to add logs to.

    Returns:
      The input job object with additional details about the execution.
    """
    current = self.m.buildbucket.build.builder
    led_data = self.m.led(
        "get-builder",
        "luci.%s.%s:%s" % (current.project, current.bucket, current.builder),
    )
    edit_args = []
    for k, v in job.properties.iteritems():
      edit_args.extend(["-p", "%s=%s" % (k, self.m.json.dumps(v))])
    for k, v in job.dimensions.iteritems():
      edit_args.extend(["-d", "%s=%s" % (k, v)])
    led_data = led_data.then("edit", *edit_args)
    led_data = self.m.led.inject_input_recipes(led_data)
    final = led_data.then("launch", "-modernize")

    job.task_id = final.launch_result.task_id
    job.task_server = final.launch_result.swarming_hostname

    presentation.links[job.name] = job.milo_url
    return job

  def collect(self, jobs, presentation):
    """Collects execution metadata for a list of jobs.

    Args:
      jobs (list(Job)): The jobs to collect information for.
      presentation (StepPresentation): The presentation to add logs to.

    Returns:
      The input jobs with additional details collected from execution.
    """
    by_task_id = {job.task_id: job for job in jobs}
    swarming_results = self.m.swarming.collect(
        "collect",
        by_task_id.keys(),
        output_dir=self.m.path["cleanup"],
    )
    for result in swarming_results:
      job = by_task_id[result.id]
      job.task_result = result

      # Led launch ensures this file is present in the task root dir.
      build_proto_path = result.output_dir.join("build.proto.json")
      build_proto_json = self.m.file.read_text("read build.proto.json",
                                               build_proto_path)
      build_proto = build_pb2.Build()
      json_format.Parse(build_proto_json, build_proto)
      job.build_proto = build_proto

      if result.success:
        job.outcome = "success"
      elif not result.state:
        job.outcome = "none"
      else:
        # Example result.state: TaskState.COMPLETED
        job.outcome = str(result.state)[10:].lower()

      presentation.links["%s (%s)" % (job.name, job.outcome)] = job.milo_url
    return jobs
