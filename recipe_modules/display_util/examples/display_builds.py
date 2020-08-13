# Copyright 2020 The Fuchsia Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from PB.go.chromium.org.luci.buildbucket.proto import common as common_pb2

DEPS = [
    "flutter/display_util",
    "fuchsia/status_check",
    "recipe_engine/buildbucket",
]


def RunSteps(api):
  builds = api.buildbucket.collect_builds(build_ids=[
      123456789012345678,
      987654321098765432,
      112233445566778899,
      199887766554433221,
  ])
  api.display_util.display_builds(
      step_name="display builds",
      builds=builds.values(),
      raise_on_failure=True,
  )


def GenTests(api):
  yield (
      api.status_check.test(
          "mixed_with_infra_failures", status="infra_failure") +
      # Exercise all status colors.
      # Purple failures prioritized over red failures.
      api.buildbucket.simulated_collect_output([
          api.buildbucket.ci_build_message(
              build_id=123456789012345678,
              status="SUCCESS",
          ),
          api.buildbucket.ci_build_message(
              build_id=987654321098765432,
              status="INFRA_FAILURE",
          ),
          api.buildbucket.ci_build_message(
              build_id=112233445566778899,
              status="FAILURE",
          ),
          api.buildbucket.ci_build_message(
              build_id=199887766554433221,
              status="SCHEDULED",
          ),
      ]))

  yield (
      api.status_check.test("mixed_without_infra_failures", status="failure") +
      # With just red failures, raise red.
      api.buildbucket.simulated_collect_output([
          api.buildbucket.ci_build_message(
              build_id=123456789012345678,
              status="SUCCESS",
          ),
          api.buildbucket.ci_build_message(
              build_id=987654321098765432,
              status="FAILURE",
          ),
          api.buildbucket.ci_build_message(
              build_id=112233445566778899,
              status="FAILURE",
          ),
          api.buildbucket.ci_build_message(
              build_id=199887766554433221,
              status="SCHEDULED",
          ),
      ]))
