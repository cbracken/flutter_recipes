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
    'flutter/os_utils',
    'flutter/repo_util',
    'flutter/flutter_deps',
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
  source_dir = checkout.join('flutter')
  isolate_source = isolate_dir.join('flutter')
  api.file.copytree('Copy source', build_dir, isolate_source)
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
  # Collect memory/cpu/process before task execution.
  api.os_utils.collect_os_info()
  """Steps to checkout flutter engine and execute web tests."""
  cache_root = api.path['cache'].join('builder')
  checkout = GetCheckoutPath(api)

  if properties.clobber:
    api.file.rmtree('Clobber cache', cache_root)
  api.file.rmtree('Clobber build output', checkout.join('out'))

  api.file.ensure_directory('Ensure checkout cache', cache_root)
  api.goma.ensure()
  dart_bin = checkout.join(
      'third_party', 'dart', 'tools', 'sdks', 'dart-sdk', 'bin'
  )

  env = {'GOMA_DIR': api.goma.goma_dir, 'ENGINE_PATH': cache_root}
  env_prefixes = {'PATH': [dart_bin]}

  # Checkout source code and build
  api.repo_util.engine_checkout(cache_root, env, env_prefixes)
  with api.context(cwd=cache_root, env=env,
                   env_prefixes=env_prefixes), api.depot_tools.on_path():

    api.gclient.runhooks()

    target_name = 'host_debug_unopt'
    gn_flags = ['--unoptimized', '--full-dart-sdk']

    RunGN(api, *gn_flags)
    Build(api, target_name)

    # Archive build directory into isolate.
    isolated_hash = Archive(api, target_name)
    ref = 'refs/heads/master'
    url = 'https://github.com/flutter/flutter'

    # Checkout flutter to run the web integration tests with the local engine.
    flutter_checkout_path = api.path['cache'].join('flutter')
    api.repo_util.checkout(
        'flutter', checkout_path=flutter_checkout_path, url=url, ref=ref
    )
    env['FLUTTER_CLONE_REPO_PATH'] = flutter_checkout_path

    with api.context(cwd=cache_root, env=env, env_prefixes=env_prefixes):
      configure_script = checkout.join(
          'flutter',
          'tools',
          'configure_framework_commit.sh',
      )
      api.step('configure framework commit', [configure_script])
      commit_no_file = flutter_checkout_path.join('flutter_ref.txt',)
      ref = api.file.read_text(
          'read commit no', commit_no_file, 'b6efc758213fdfffee1234465'
      )
      assert (len(ref) > 0)
    # The SHA of the youngest commit older than the engine in the framework
    # side is kept in `ref`.
    builds = schedule_builds(api, isolated_hash, ref.strip(), url)

  # Create new enviromenent variables for Framework.
  # Note that the `dart binary` location is not the same for Framework and the
  # engine.
  f_env, f_env_prefix = api.repo_util.flutter_environment(flutter_checkout_path)

  deps = [{'dependency': 'chrome_and_driver'}, {"dependency": "curl"}]
  api.flutter_deps.required_deps(f_env, f_env_prefix, deps)

  integration_test = flutter_checkout_path.join(
      'dev', 'integration_tests', 'web'
  )

  with api.context(cwd=integration_test, env=f_env,
                   env_prefixes=f_env_prefix), api.step.defer_results():
    build_dir = checkout.join('out', target_name)
    api.step(
        'web integration tests config', [
            'flutter',
            'config',
            '--local-engine=%s' % build_dir,
            '--no-analytics',
            '--enable-web',
        ]
    )
    api.step(
        'run web integration tests', [
            'flutter',
            '--local-engine=%s' % build_dir,
            'build',
            'web',
            '-v',
        ]
    )

    # This is to clean up leaked processes.
    api.os_utils.kill_processes()
    # Collect memory/cpu/process after task execution.
    api.os_utils.collect_os_info()

  with api.context(cwd=cache_root, env=env, env_prefixes=env_prefixes):
    builds = api.shard_util.collect_builds(builds)
    api.display_util.display_builds(
        step_name='display builds',
        builds=builds,
        raise_on_failure=True,
    )


def schedule_builds(api, isolated_hash, ref, url):
  """Schedules one subbuild per subshard."""
  reqs = []

  shard = api.properties.get('shard')
  dependencies = [{'dependency': 'chrome_and_driver'}]
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
  yield api.test(
      'linux-pre-submit',
      api.repo_util.flutter_environment_data(api.path['cache'].join('flutter')),
      api.properties(
          dependencies=[{'dependency': 'chrome_and_driver'}],
          shard='web_tests',
          subshards=['0', '1_last'],
          goma_jobs='200',
          git_url='https://mygitrepo',
          git_ref='refs/pull/1/head',
          clobber=True,
          task_name='abc'
      ),
      api.platform('linux', 64),
  )
