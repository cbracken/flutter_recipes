# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import re

from PB.recipes.flutter.engine import InputProperties
from PB.recipes.flutter.engine import EnvProperties

DEPS = [
    'depot_tools/depot_tools',
    'depot_tools/gclient',
    'flutter/bucket_util',
    'flutter/os_utils',
    'flutter/repo_util',
    'fuchsia/goma',
    'recipe_engine/buildbucket',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/raw_io',
    'recipe_engine/step',
]

PROPERTIES = InputProperties
ENV_PROPERTIES = EnvProperties


def GetCheckoutPath(api):
  return api.path['cache'].join('builder', 'src')


def Build(api, config, *targets):
  checkout = GetCheckoutPath(api)
  build_dir = checkout.join('out', config)
  goma_jobs = api.properties['goma_jobs']
  ninja_args = [api.depot_tools.ninja_path, '-j', goma_jobs, '-C', build_dir]
  ninja_args.extend(targets)
  with api.goma.build_with_goma():
    name = 'build %s' % ' '.join([config] + list(targets))
    api.step(name, ninja_args)


def RunGN(api, *args):
  checkout = GetCheckoutPath(api)
  gn_cmd = ['python', checkout.join('flutter/tools/gn'), '--goma']
  gn_cmd.extend(args)
  api.step('gn %s' % ' '.join(args), gn_cmd)


def RunAndroidScenarioTests(api):
  """Runs the scenario test app on a x86 Android emulator.

  See details at
  https://chromium.googlesource.com/chromium/src/+/HEAD/docs/android_emulator.md#using-your-own-emulator-image
  """
  engine_checkout = GetCheckoutPath(api)
  android_tool_dir = engine_checkout.join('tools', 'android')

  api.cipd.ensure(
      android_tool_dir,
      api.cipd.EnsureFile().add_package(
          'chromium/tools/android/avd',
          'a1SpJpmu4ReL4-4fR02ZV4FjhWb4z3p88a408gvfFWcC'
      )
  )

  avd_script_path = android_tool_dir.join(
      'src', 'tools', 'android', 'avd', 'avd.py'
  )

  avd_config = android_tool_dir.join(
      'src', 'tools', 'android', 'avd', 'proto', 'generic_android28.textpb'
  )

  emulator_pid = ''
  with api.context(cwd=android_tool_dir):
    api.python(
        'Install Android emulator (API level 28)', avd_script_path,
        ['install', '--avd-config', avd_config]
    )

    output = api.python(
        'Start Android emulator (API level 28)',
        avd_script_path,
        ['start', '--no-read-only', '--avd-config', avd_config],
        stdout=api.raw_io.output()
    ).stdout
    m = re.match('.*pid: (\d+)\)', output)
    emulator_pid = m.group(1)
  test_dir = engine_checkout.join('flutter', 'testing')
  scenario_app_tests = test_dir.join('scenario_app')

  # Proxies `python` since vpython cannot resolve spec files outside of the jar
  # file containing the python scripts.
  gradle_home_bin_dir = scenario_app_tests.join('android', 'gradle-home', 'bin')
  with api.context(cwd=scenario_app_tests,
                   env_prefixes={'PATH': [gradle_home_bin_dir]}):

    result = api.step(
        'Scenario App Integration Tests',
        ['./build_and_run_android_tests.sh', 'android_debug_x86'],
        ok_ret='all'
    )
    api.step('Kill emulator', ['kill', '-9', emulator_pid])
    build_failures_dir = scenario_app_tests.join('build', 'reports', 'failures')
    if result.exc_result.retcode != 0 and api.path.exists(build_failures_dir):
      # Upload any diff failures.
      # If there are any, upload them to the cloud bucket.
      api.bucket_util.upload_folder(
          'Upload diff failures', 'src/flutter/testing/scenario_app',
          'build/reports/diff_failures', 'diff_failures.zip'
      )
      raise AssertionError('Diff detected. Please verify the diff failures.')


def RunSteps(api, properties, env_properties):
  # Collect memory/cpu/process after task execution.
  api.os_utils.collect_os_info()

  cache_root = api.path['cache'].join('builder')
  checkout = GetCheckoutPath(api)

  api.file.rmtree('Clobber build output', checkout.join('out'))
  api.file.ensure_directory('Ensure checkout cache', cache_root)
  api.goma.ensure()

  dart_bin = checkout.join(
      'third_party', 'dart', 'tools', 'sdks', 'dart-sdk', 'bin'
  )
  android_home = checkout.join('third_party', 'android_tools', 'sdk')
  env = {'GOMA_DIR': api.goma.goma_dir, 'ANDROID_HOME': str(android_home)}
  env_prefixes = {'PATH': [dart_bin]}

  api.repo_util.engine_checkout(
      cache_root, env, env_prefixes, clobber=properties.clobber
  )

  with api.step.nest('Android SDK Licenses'):
    api.file.ensure_directory('mkdir licenses', android_home.join('licenses'))
    api.file.write_text(
        'android sdk license',
        android_home.join('licenses', 'android-sdk-license'),
        str(properties.android_sdk_license)
    )
    api.file.write_text(
        'android sdk preview license',
        android_home.join('licenses', 'android-sdk-preview-license'),
        str(properties.android_sdk_preview_license)
    )

  with api.context(cwd=cache_root, env=env,
                   env_prefixes=env_prefixes), api.depot_tools.on_path():
    RunGN(api, '--runtime-mode', 'debug', '--unoptimized')
    Build(api, 'host_debug_unopt')

    RunGN(api, '--android', '--android-cpu=x86', '--no-lto')
    Build(api, 'android_debug_x86')

    RunAndroidScenarioTests(api)

  with api.step.defer_results():
    # This is to clean up leaked processes.
    api.os_utils.kill_processes()
    # Collect memory/cpu/process after task execution.
    api.os_utils.collect_os_info()


def GenTests(api):
  scenario_failures = GetCheckoutPath(api).join(
      'flutter', 'testing', 'scenario_app', 'build', 'reports', 'failures'
  )
  for upload_packages in (True, False):
    yield api.test(
        'without_failure_upload_%d' % upload_packages,
        api.buildbucket.ci_build(
            builder='Linux Engine',
            git_repo='https://chromium.googlesource.com/external/github.com/flutter/engine',
            project='flutter',
            revision='abcd1234',
        ),
        api.properties(
            InputProperties(
                android_sdk_license='android_sdk_hash',
                goma_jobs='1024',
                upload_packages=upload_packages,
            ),
        ), api.path.exists(scenario_failures),
        api.step_data(
            'Start Android emulator (API level 28)',
            stdout=api.raw_io.output_text(
                'android_28_google_apis_x86|emulator-5554 started (pid: 17687)'
            )
        )
    )
    test = api.test(
        'with_failure_upload_%d' % upload_packages,
        api.buildbucket.ci_build(
            builder='Linux Engine',
            git_repo='https://chromium.googlesource.com/external/github.com/flutter/engine',
            project='flutter',
            revision='abcd1234',
        ),
        api.properties(
            InputProperties(
                android_sdk_license='android_sdk_hash',
                goma_jobs='1024',
                upload_packages=upload_packages,
                clobber=False,
            ),
        ),
        # Makes the test fail.
        api.step_data('Scenario App Integration Tests', retcode=1),
        api.path.exists(scenario_failures),
        api.expect_exception('AssertionError'),
        api.step_data(
            'Start Android emulator (API level 28)',
            stdout=api.raw_io.output_text(
                'android_28_google_apis_x86|emulator-5554 started (pid: 17687)'
            )
        )
    )
    if upload_packages:
      test += api.step_data(
          'Ensure flutter/abcd1234/diff_failures.zip does not already exist on cloud storage',
          retcode=1
      )
    yield test
