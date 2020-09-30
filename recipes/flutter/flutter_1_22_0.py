# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
import re

from PB.go.chromium.org.luci.buildbucket.proto import build as build_pb2
from PB.go.chromium.org.luci.buildbucket.proto import common as common_pb2
from PB.go.chromium.org.luci.buildbucket.proto \
  import builds_service as builds_service_pb2
from google.protobuf import struct_pb2

DEPS = [
    'flutter/android_sdk',
    'flutter/adhoc_validation',
    'flutter/json_util',
    'flutter/repo_util',
    'flutter/shard_util',
    'flutter/flutter_deps',
    'flutter/display_util',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/step',
]


def RunSteps(api):
  """Recipe to run flutter sdk tests."""
  # Trigger sharded tests.
  if not api.properties.get('validation'):
    builds = api.shard_util.schedule_builds()
    builds = api.shard_util.collect_builds(builds)
    api.display_util.display_builds(
        step_name='display builds',
        builds=builds,
        raise_on_failure=True,
    )
    return

  # Trigger validation tests. This is to optimize resources usage
  # when don't need to run in shards.
  checkout_path = api.path['start_dir'].join('flutter')
  with api.step.nest('checkout source code'):
    api.repo_util.checkout(
        'flutter',
        checkout_path=checkout_path,
        url=api.properties.get('git_url'),
        ref=api.properties.get('git_ref')
    )

  if api.platform.is_linux:
    # Validates flutter builders json format.
    api.json_util.validate_json(checkout_path)

  env, env_prefixes = api.repo_util.flutter_environment(checkout_path)
  api.flutter_deps.required_deps(
      env, env_prefixes, api.properties.get('dependencies', [])
  )
  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout_path):
    with api.step.nest('prepare environment'):
      api.step('flutter doctor', ['flutter', 'doctor'])
      api.step('download dependencies', ['flutter', 'update-packages'])
      api.adhoc_validation.run(
          api.properties.get('validation_name'),
          api.properties.get('validation'), env, env_prefixes,
          api.properties.get('secrets', {})
      )


def GenTests(api):
  yield api.test(
      'validators',
      api.properties(
          validation='analyze',
          validation_name='dart analyze',
          android_sdk_license='android_license',
          android_sdk_preview_license='android_preview_license'
      ), api.repo_util.flutter_environment_data()
  )
  props = struct_pb2.Struct()
  props['task_name'] = 'abc'
  build = build_pb2.Build(input=build_pb2.Build.Input(properties=props))
  passed_batch_res = builds_service_pb2.BatchResponse(
      responses=[
          dict(
              schedule_build=dict(
                  id=build.id, builder=build.builder, input=build.input
              )
          )
      ]
  )
  yield api.test(
      'shards',
      api.properties(shard='framework_tests', subshards=['0', '1_last']),
      api.repo_util.flutter_environment_data(),
      api.buildbucket.simulated_schedule_output(passed_batch_res)
  )

  err_batch_res = builds_service_pb2.BatchResponse(
      responses=[
          dict(error=dict(
              code=1,
              message='bad',
          ),),
      ],
  )
  yield api.test(
      'shards_fail',
      api.properties(shard='framework_tests', subshards=['0', '1_last']),
      api.repo_util.flutter_environment_data(),
      api.buildbucket.simulated_schedule_output(err_batch_res)
  )
