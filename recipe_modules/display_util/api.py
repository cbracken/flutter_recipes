# Copyright 2020 The Fuchsia Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

from PB.go.chromium.org.luci.buildbucket.proto import common as common_pb2

from RECIPE_MODULES.fuchsia.utils import pluralize


class DisplayUtilApi(recipe_api.RecipeApi):
  """Module to display buildbucket or swarming tasks as steps."""

  def display_builds(self, step_name, builds, raise_on_failure=False):
    """Display build links and status for each input build.

        Optionally raise on build failure(s).

        Args:
          step_name (str): Name of build group to display in step name.
          builds (seq(buildbucket.v2.Build)): buildbucket Build objects. See
            recipe_engine/buildbucket recipe module for more info.
          raise_on_failure (bool): Raise InfraFailure or StepFailure on failure.

        Raises:
          InfraFailure: One or more input builds had infra failure. Takes priority
            over step failures.
          StepFailure: One or more of input builds failed.
        """
    # List of failed builds
    infra_failures = []
    failures = []
    # Create per-build display steps.
    with self.m.step.nest(step_name) as presentation:
      for k in builds:
        build = builds[k] if isinstance(k, long) or isinstance(k, int) else k
        with self.m.step.nest(build.builder.builder) as display_step:
          step_links = display_step.presentation.links
          step_links[str(build.id)
                    ] = self.m.buildbucket.build_url(build_id=build.id)
          if build.status == common_pb2.Status.Value('SUCCESS'):
            display_step.presentation.status = self.m.step.SUCCESS
          elif build.status == common_pb2.Status.Value('INFRA_FAILURE'):
            display_step.presentation.status = self.m.step.EXCEPTION
            infra_failures.append(build)
          elif build.status == common_pb2.Status.Value('FAILURE'):
            display_step.presentation.status = self.m.step.FAILURE
            failures.append(build)
          # For any other status, use warning color.
          else:
            display_step.presentation.status = self.m.step.WARNING

      def summary_section(build):
        url = self.m.buildbucket.build_url(build_id=build.id)
        failure_header = "[%s](%s)" % (build.builder.builder, url)
        if build.status == common_pb2.INFRA_FAILURE:
          failure_header += " (infra failure)"
        summary = build.summary_markdown.strip()
        # Don't include an empty summary.
        if not summary:
          return failure_header
        return failure_header + ":\n\n%s" % summary

      failure_message_parts = []
      for b in infra_failures + failures:
        failure_message_parts.append(summary_section(b))

      if raise_on_failure:
        # If there were any infra failures, raise purple.
        if infra_failures:
          presentation.status = self.m.step.EXCEPTION
          exception_type = self.m.step.InfraFailure
        # Otherwise if there were any step failures, raise red.
        elif failures:
          presentation.status = self.m.step.FAILURE
          exception_type = self.m.step.StepFailure
        else:
          return

        num_failed = len(failures) + len(infra_failures)
        raise exception_type(
            "%s failed:\n\n%s" % (
                pluralize("build",
                          num_failed), "\n\n".join(failure_message_parts)
            )
        )

  def display_tasks(self, step_name, results, metadata, raise_on_failure=False):
    """Display task links and status for each input task.

        Optionally raise on build failure(s).

        Args:
          step_name (str): Name of build group to display in step name.
          results (seq(swarming.TaskResult)): swarming TaskResult objects. See
            recipe_engine/swarming recipe module for more info.
          metadata (seq(swarming.TaskMetadata)): swarming TaskMetadata objects. See
            recipe_engine/swarming recipe module for more info.
          raise_on_failure (bool): Raise InfraFailure or StepFailure on failure.

        Raises:
          InfraFailure: One or more input builds had infra failure. Takes priority
            over step failures.
          StepFailure: One or more of input builds failed.
        """
    self._display(
        step_name=step_name,
        builds=results,
        raise_on_failure=raise_on_failure,
        process_func=self._process_task,
        metadata=metadata,
    )

  def _process_task(
      self, result, infra_failed_builders, failed_builders, links
  ):
    """Process a single swarming.TaskResult.

        Args:
          result (swarming.TaskResult): A swarming TaskResult object.
          infra_failed_builders (List(str)): A list of the builder names with infra failures.
          failed_builders (List(str)): A list of the builder names with failures.
          links (Dict): A dictionary with the task links as values and the task id as keys.
        """
    with self.m.step.nest(result.name) as display_step:
      step_links = display_step.presentation.links
      step_links[str(result.id)] = links[result.id]
      if (result.state is None or
          result.state != self.m.swarming.TaskState.COMPLETED):
        display_step.status = self.m.step.EXCEPTION
        infra_failed_builders.append(result.name)
      elif not result.success:
        display_step.status = self.m.step.FAILURE
        failed_builders.append(result.name)
      else:
        display_step.presentation.status = self.m.step.WARNING

  def _display(
      self,
      step_name,
      builds,
      process_func,
      raise_on_failure=False,
      metadata=None
  ):
    """Display build links and status for each input build.

        Optionally raise on build failure(s).

        Args:
          step_name (str): Name of build group to display in step name.
          builds (seq(buildbucket.v2.Build) or seq(swarming.TaskResult)): buildbucket Build or swarming TaskResult objects. See
            recipe_engine/buildbucket or recipe_engine/swarming recipe module for more info.
          process_func (Runnable): A function to process a build or task result object.
          raise_on_failure (bool): Raise InfraFailure or StepFailure on failure.
          metadata (seq(swarming.TaskMetadata)): swarming TaskMetadata objects. See
            recipe_engine/swarming recipe module for more info.

        Raises:
          InfraFailure: One or more input builds had infra failure. Takes priority
            over step failures.
          StepFailure: One or more of input builds failed.
        """
    infra_failed_builders = []
    failed_builders = []
    # Create per-build display steps.
    with self.m.step.nest(step_name):
      for k in builds:
        build = builds[k] if isinstance(k, long) or isinstance(k, int) else k
        args = {
            "result": build,
            "infra_failed_builders": infra_failed_builders,
            "failed_builders": failed_builders,
        }
        if metadata:
          args["links"] = {m.id: m.task_ui_link for m in metadata}
        process_func(**args)

      if raise_on_failure:
        # Construct failure header and message. Include both types of failures,
        # regardless of whether we raise purple or red.
        failure_header = "build(s) failed"
        failure_message = []
        if infra_failed_builders:
          failure_message.append(
              "infra failures: {infra_failed_builders}".format(
                  infra_failed_builders=", ".join(infra_failed_builders)
              )
          )
        if failed_builders:
          failure_message.append(
              "step failures: {failed_builders}".format(
                  failed_builders=", ".join(failed_builders)
              )
          )
        failure_message = ", ".join(failure_message)
        # If there were any infra failures, raise purple.
        if infra_failed_builders:
          self.m.python.infra_failing_step(
              failure_header,
              failure_message,
          )
        # Otherwise if there were any step failures, raise red.
        if failed_builders:
          self.m.python.failing_step(
              failure_header,
              failure_message,
          )
