# Copyright 2020 The Fuchsia Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from PB.go.chromium.org.luci.buildbucket.proto import common as common_pb2
from recipe_engine.recipe_api import Property

DEPS = [
    "flutter/display_util",
    "fuchsia/status_check",
    "recipe_engine/buildbucket",
]

PROPERTIES = {
    "raise_on_failure": Property(kind=bool, default=True),
}

def RunSteps(api, raise_on_failure):
  builds = api.buildbucket.collect_builds(build_ids=[
      123456789012345678,
      987654321098765432,
      112233445566778899,
      199887766554433221,
  ])
  api.display_util.display_builds(
      step_name="display builds",
      builds=builds.values(),
      raise_on_failure=raise_on_failure,
  )


def GenTests(api):
  def build(summary_markdown=None, **kwargs):
      b = api.buildbucket.ci_build_message(**kwargs)
      if summary_markdown:
          b.summary_markdown = summary_markdown
      return b

  yield (
      api.status_check.test(
          "mixed_with_infra_failures", status="infra_failure") +
      # Exercise all status colors.
      # Purple failures prioritized over red failures.
      api.buildbucket.simulated_collect_output([
          build(
              build_id=123456789012345678,
              status="SUCCESS",
          ),
          build(
              build_id=987654321098765432,
              status="INFRA_FAILURE",
              summary_markdown="something failed related to infra",
          ),
          build(
              build_id=112233445566778899,
              status="FAILURE",
              summary_markdown="something failed not related to infra",
          ),
          build(
              build_id=199887766554433221,
              status="SCHEDULED",
          ),
      ]))

  yield (
      api.status_check.test("mixed_without_infra_failures", status="failure") +
      # With just red failures, raise red.
      api.buildbucket.simulated_collect_output([
          build(
              build_id=123456789012345678,
              status="SUCCESS",
          ),
          build(
              build_id=987654321098765432,
              status="FAILURE",
          ),
          build(
              build_id=112233445566778899,
              status="FAILURE",
          ),
          build(
              build_id=199887766554433221,
              status="SCHEDULED",
          ),
      ]))

  yield (
      api.status_check.test("all_passed") +
      # With just red failures, raise red.
      api.buildbucket.simulated_collect_output([
          build(
              build_id=123456789012345678,
              status="SUCCESS",
          ),
      ]))
