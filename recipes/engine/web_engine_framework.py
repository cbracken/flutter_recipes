# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Recipe for framework tests running with web-engine repository tests."""

import contextlib
import copy

from recipe_engine import recipe_api

from PB.recipes.flutter.engine import InputProperties
from PB.recipes.flutter.engine import EnvProperties

DEPS = [
    'depot_tools/bot_update',
    'depot_tools/depot_tools',
    'depot_tools/gclient',
    'depot_tools/gsutil',
    'flutter/display_util',
    'flutter/repo_util',
    'flutter/shard_util',
    'fuchsia/goma',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/isolated',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/step',
    'recipe_engine/swarming',
]

PROPERTIES = InputProperties
ENV_PROPERTIES = EnvProperties
DRONE_TIMEOUT_SECS = 3600 * 3  # 3 hours.

# Builder names use full platform name instead of short names. We need to
# map short names to full platform names to be able to identify the drone
# used to run the subshards.
PLATFORM_TO_NAME = {'win': 'Windows', 'linux': 'Linux'}


def Build(api, config, *targets):
  checkout = GetCheckoutPath(api)
  build_dir = checkout.join('out/%s' % config)
  goma_jobs = api.properties['goma_jobs']
  ninja_args = [api.depot_tools.ninja_path, '-j', goma_jobs, '-C', build_dir]
  ninja_args.extend(targets)
  with api.goma.build_with_goma():
    name = 'build %s' % ' '.join([config] + list(targets))
    api.step(name, ninja_args)

def Archive(api, target):
  checkout = GetCheckoutPath(api)
  build_dir = checkout.join('out', target)
  isolate_dir = api.path.mkdtemp('isolate-directory')
  isolate_engine = isolate_dir.join(target)
  api.file.copytree('Copy host_debug_unopt', build_dir, isolate_engine)
  isolated = api.isolated.isolated(isolate_dir)
  isolated.add_dir(isolate_dir)
  return isolated.archive('Archive Flutter Engine Test Isolate')

def RunGN(api, *args):
  checkout = GetCheckoutPath(api)
  gn_cmd = ['python', checkout.join('flutter/tools/gn'), '--goma']
  gn_cmd.extend(args)
  api.step('gn %s' % ' '.join(args), gn_cmd)

def GetCheckoutPath(api):
  return api.path['cache'].join('builder', 'src')

def RunSteps(api, properties, env_properties):
  """Steps to checkout flutter engine and execute web tests."""
  cache_root = api.path['cache'].join('builder')
  checkout = GetCheckoutPath(api)

  if properties.clobber:
    api.file.rmtree('Clobber cache', cache_root)
  api.file.rmtree('Clobber build output', checkout.join('out'))

  api.file.ensure_directory('Ensure checkout cache', cache_root)
  api.goma.ensure()
  dart_bin = checkout.join('third_party', 'dart', 'tools', 'sdks', 'dart-sdk',
                           'bin')

  env = {
      'GOMA_DIR': api.goma.goma_dir,
      'ENGINE_PATH': cache_root
  }
  env_prefixes = {'PATH': [dart_bin]}

  # Checkout source code and build
  api.repo_util.engine_checkout(cache_root, env, env_prefixes)
  with api.context(
      cwd=cache_root, env=env,
      env_prefixes=env_prefixes), api.depot_tools.on_path():

    api.gclient.runhooks()

    target_name = 'host_debug_unopt'
    gn_flags = ['--unoptimized', '--full-dart-sdk']

    RunGN(api, *gn_flags)
    Build(api, target_name)

    # Archive build directory into isolate.
    isolated_hash = Archive(api, target_name)

    builds = schedule_builds(api, isolated_hash)
    builds = api.shard_util.collect_builds(builds)
    api.display_util.display_builds(
        step_name='display builds',
        builds=builds,
        raise_on_failure=True,
    )


def schedule_builds(api, isolated_hash):
  """Schedules one subbuild per subshard."""
  reqs = []
  # TODO: Use the youngest commit older than the engine.
  ref = 'refs/heads/master'
  url = 'https://github.com/flutter/flutter'
  shard = api.properties.get('shard')
  dependencies=[{'dependency': 'chrome_and_driver'}]
  for subshard in api.properties.get('subshards'):
    task_name = '%s-%s' % (shard, subshard)
    drone_props = {
        'subshard': subshard,
        'shard': shard,
        'dependencies': dependencies,
        'task_name': task_name,
        'isolated_hash': isolated_hash,
    }
    drone_props['git_url'] = url
    drone_props['git_ref'] = ref
    platform_name = PLATFORM_TO_NAME.get(api.platform.name)
    req = api.buildbucket.schedule_request(
        swarming_parent_run_id=api.swarming.task_id,
        builder='%s SDK Drone' % platform_name,
        properties=drone_props,
        priority=25
    )
    reqs.append(req)
  return api.buildbucket.schedule(reqs)

def GenTests(api):
  yield api.test('linux-pre-submit') + api.properties(
      dependencies=['chrome_and_drivers'],
      shard='web_tests',
      subshards=['0', '1_last'],
      goma_jobs='200',
      git_url='https://mygitrepo',
      git_ref='refs/pull/1/head',
      clobber=True) + api.platform('linux', 64)
