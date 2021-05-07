# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe for engine repository tests."""

import contextlib
import copy

from recipe_engine import recipe_api

from PB.recipes.flutter.engine import InputProperties
from PB.recipes.flutter.engine import EnvProperties

DEPS = [
    'depot_tools/bot_update',
    'depot_tools/depot_tools',
    'depot_tools/gclient',
    'depot_tools/git',
    'depot_tools/gsutil',
    'flutter/display_util',
    'flutter/flutter_deps',
    'flutter/json_util',
    'flutter/os_utils',
    'flutter/osx_sdk',
    'flutter/repo_util',
    'flutter/shard_util',
    'flutter/web_util',
    'flutter/yaml',
    'fuchsia/goma',
    'recipe_engine/buildbucket',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/isolated',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/runtime',
    'recipe_engine/step',
    'recipe_engine/swarming',
]

GIT_REPO = (
    'https://chromium.googlesource.com/external/github.com/flutter/engine'
)

PROPERTIES = InputProperties
ENV_PROPERTIES = EnvProperties


@contextlib.contextmanager
def SetupXcode(api):
  # See cr-buildbucket.cfg for how the version is passed in.
  # https://github.com/flutter/infra/blob/master/config/cr-buildbucket.cfg#L148
  with api.osx_sdk('ios'):
    yield


def Build(api, config, *targets):
  checkout = GetCheckoutPath(api)
  build_dir = checkout.join('out/%s' % config)
  goma_jobs = api.properties['goma_jobs']
  ninja_args = [api.depot_tools.ninja_path, '-j', goma_jobs, '-C', build_dir]
  ninja_args.extend(targets)
  with api.goma.build_with_goma():
    name = 'build %s' % ' '.join([config] + list(targets))
    api.step(name, ninja_args)


def FormatAndDartTest(api):
  checkout = GetCheckoutPath(api)
  with api.context(cwd=checkout.join('flutter')):
    format_cmd = checkout.join('flutter', 'ci', 'format.sh')
    api.step('format and dart test', [format_cmd])


def Lint(api):
  checkout = GetCheckoutPath(api)
  with api.context(cwd=checkout):
    lint_cmd = checkout.join('flutter', 'ci', 'lint.sh')
    api.step('lint test', [lint_cmd])


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


def CleanUpProcesses(api):
  # This is to clean up leaked processes.
  api.os_utils.kill_processes()
  # Collect memory/cpu/process after task execution.
  api.os_utils.collect_os_info()


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

  android_home = checkout.join('third_party', 'android_tools', 'sdk')

  env = {
      'GOMA_DIR': api.goma.goma_dir, 'ANDROID_HOME': str(android_home),
      'CHROME_NO_SANDBOX': 'true', 'ENGINE_PATH': cache_root
  }
  env_prefixes = {'PATH': [dart_bin]}

  api.flutter_deps.certs(env, env_prefixes)

  # Enable long path support on Windows.
  api.flutter_deps.enable_long_paths(env, env_prefixes)

  # Checkout source code and build
  api.repo_util.engine_checkout(cache_root, env, env_prefixes)

  if api.platform.is_mac:
    api.web_util.clone_goldens_repo(checkout)

  with api.context(cwd=cache_root, env=env,
                   env_prefixes=env_prefixes), api.depot_tools.on_path():

    # Checks before building the engine. Only run on Linux.
    if api.platform.is_linux:
      api.json_util.validate_json(checkout.join('flutter', 'ci'))
      FormatAndDartTest(api)
      Lint(api)

    api.gclient.runhooks()

    target_name = 'host_debug_unopt'
    gn_flags = ['--unoptimized', '--full-dart-sdk']
    # Mac needs to install xcode as part of the building process.
    additional_args = []
    felt_cmd = [
        checkout.join('out', target_name, 'dart-sdk', 'bin', 'dart'),
        'dev/felt.dart'
    ]

    isolated_hash = ''
    builds = []
    if api.platform.is_linux:
      RunGN(api, *gn_flags)
      Build(api, target_name)
      # Archieve the engine. Start the drones. Due to capacity limits we are
      # Only using the drones on the Linux for now.
      # Archive build directory into isolate.
      isolated_hash = Archive(api, target_name)
      # Schedule builds.
      # TODO(nurhan): Currently this recipe only shards Linux. The web drones
      # recipe is written in a way that it can also support sharding for
      # macOS and Windows OSes. When more resources are available or when
      # MWE or WWE builders start running more than 1 hour, also shard those
      # builders.
      builds = schedule_builds_on_linux(api, isolated_hash)
    elif api.platform.is_mac:
      with SetupXcode(api):
        RunGN(api, *gn_flags)
        Build(api, target_name)
        additional_args = ['--browser', 'ios-safari']
    else:
      # Platform = windows.
      RunGN(api, *gn_flags)
      Build(api, target_name)
      if api.platform.is_win:
        felt_cmd = [
            checkout.join(
                'flutter', 'lib', 'web_ui', 'dev', 'felt_windows.bat'
            )
        ]

    # Update dart packages and run tests.
    local_pub = checkout.join('out', target_name, 'dart-sdk', 'bin', 'pub')
    with api.context(
        cwd=checkout.join('flutter', 'web_sdk', 'web_engine_tester')):
      api.step('pub get in web_engine_tester', [local_pub, 'get'])
    with api.context(cwd=checkout.join('flutter', 'lib', 'web_ui')):
      api.step('pub get in web_engine_tester', [local_pub, 'get'])
      # TODO(nurhan): carry licenses to another shard when we have more
      # resources.
      felt_licenses = copy.deepcopy(felt_cmd)
      felt_licenses.append('check-licenses')
      api.step('felt licenses', felt_licenses)
      if api.platform.is_mac:
        additional_args_safari_desktop = ['--browser', 'safari']
        felt_test_safari_desktop = copy.deepcopy(felt_cmd)
        felt_test_safari_desktop.append('test')
        felt_test_safari_desktop.extend(additional_args_safari_desktop)
        api.step('felt test safari desktop', felt_test_safari_desktop)
      if api.platform.is_linux:
        # TODO(nurhan): Web engine analysis can also be part of felt and used
        # in a shard.
        web_engine_analysis_cmd = [
            checkout.join(
                'flutter', 'lib', 'web_ui', 'dev', 'web_engine_analysis.sh'
            ),
        ]
        api.step('web engine analysis', web_engine_analysis_cmd)
        builds = api.shard_util.collect_builds(builds)
        api.display_util.display_builds(
            step_name='display builds',
            builds=builds,
            raise_on_failure=True,
        )
        CleanUpProcesses(api)
      elif api.platform.is_mac:
        with SetupXcode(api):
          with recipe_api.defer_results():
            felt_test = copy.deepcopy(felt_cmd)
            felt_test.append('test')
            felt_test.extend(additional_args)
            api.step('felt ios-safari test', felt_test)
            api.web_util.upload_failing_goldens(checkout, 'ios-safari')
            CleanUpProcesses(api)
      else:
        api.web_util.chrome(checkout)
        felt_test = copy.deepcopy(felt_cmd)
        felt_test.append('test')
        felt_test.extend(additional_args)
        api.step('felt test chrome', felt_test)
        CleanUpProcesses(api)


def schedule_builds_on_linux(api, isolated_hash):
  """Schedules one subbuild per subshard."""
  reqs = []

  # For running Chrome Integration tests:
  command_name = 'chrome-integration-linux'
  # These are the required dependencies.
  dependencies = ['chrome', 'chrome_driver', 'goldens_repo']
  # These are the felt commands which will be used.
  command_args = ['test', '--browser=chrome', '--integration-tests-only']
  addShardTask(
      api, reqs, command_name, dependencies, command_args, isolated_hash
  )

  # For running Chrome Unit tests:
  command_name = 'chrome-unit-linux'
  # These are the required dependencies.
  dependencies = ['chrome', 'goldens_repo']
  # These are the felt commands which will be used.
  command_args = ['test', '--browser=chrome', '--unit-tests-only']
  addShardTask(
      api, reqs, command_name, dependencies, command_args, isolated_hash
  )

  # For running Firefox Unit tests:
  command_name = 'firefox-unit-linux'
  # We don't need extra dependencies since felt tools handles firefox itself.
  # TODO(nurhan): Use cipd packages for Firefox. As we are doing for chrome
  # still respect to the version from browser_lock.yaml.
  dependencies = []
  # These are the felt commands which will be used.
  command_args = ['test', '--browser=firefox', '--unit-tests-only']
  addShardTask(
      api, reqs, command_name, dependencies, command_args, isolated_hash
  )

  # For running Firefox Integration tests:
  command_name = 'firefox-integration-linux'
  # These are the required dependencies.
  dependencies = ['firefox_driver', 'goldens_repo']
  # These are the felt commands which will be used.
  command_args = ['test', '--browser=firefox', '--integration-tests-only']
  addShardTask(
      api, reqs, command_name, dependencies, command_args, isolated_hash
  )

  return api.buildbucket.schedule(reqs)


def addShardTask(
    api, reqs, command_name, dependencies, command_args, isolated_hash
):
  drone_props = {
      'command_name': command_name, 'dependencies': dependencies,
      'command_args': command_args, 'isolated_hash': isolated_hash
  }

  git_url = GIT_REPO
  git_ref = api.buildbucket.gitiles_commit.ref
  if 'git_url' in api.properties and 'git_ref' in api.properties:
    git_url = api.properties['git_url']
    git_ref = api.properties['git_ref']

  drone_props['git_url'] = git_url
  if not git_ref:
    drone_props['git_ref'] = 'refs/heads/master'
  else:
    drone_props['git_ref'] = git_ref

  req = api.buildbucket.schedule_request(
      swarming_parent_run_id=api.swarming.task_id,
      builder='Linux Web Drone',
      properties=drone_props,
      priority=25
  )
  reqs.append(req)


def GenTests(api):
  browser_yaml_file = {
      'required_driver_version': {'chrome': 84},
      'chrome': {'Linux': '768968', 'Mac': '768985', 'Win': '768975'}
  }
  golden_yaml_file = {'repository': 'repo', 'revision': 'b6efc758'}
  yield api.test('linux-post-submit') + api.properties(
      goma_jobs='200'
  ) + api.platform('linux', 64) + api.runtime(is_experimental=False)
  yield api.test(
      'windows-post-submit',
      api.step_data(
          'read browser lock yaml.parse', api.json.output(browser_yaml_file)
      ), api.properties(goma_jobs='200'), api.platform('win', 64)
  ) + api.runtime(is_experimental=False)
  yield api.test(
      'mac-post-submit',
      api.step_data('read yaml.parse', api.json.output(golden_yaml_file)),
      api.properties(goma_jobs='200'), api.platform('mac', 64)
  ) + api.runtime(is_experimental=False)
  yield api.test('linux-pre-submit') + api.properties(
      goma_jobs='200',
      git_url='https://mygitrepo',
      git_ref='refs/pull/1/head',
      gcs_goldens_bucket='mybucket',
      clobber=True
  ) + api.platform('linux', 64) + api.runtime(is_experimental=False)
