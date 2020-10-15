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
    'depot_tools/osx_sdk',
    'flutter/os_utils',
    'flutter/json_util',
    'flutter/repo_util',
    'flutter/yaml',
    'fuchsia/goma',
    'recipe_engine/buildbucket',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/runtime',
    'recipe_engine/step',
]

GIT_REPO = (
    'https://chromium.googlesource.com/external/github.com/flutter/engine')

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


def RunGN(api, *args):
  checkout = GetCheckoutPath(api)
  gn_cmd = ['python', checkout.join('flutter/tools/gn'), '--goma']
  gn_cmd.extend(args)
  api.step('gn %s' % ' '.join(args), gn_cmd)


def GetCheckoutPath(api):
  return api.path['cache'].join('builder', 'src')


def DownloadFirefoxDriver(api):
  checkout = GetCheckoutPath(api)
  # Download the driver for Firefox.
  firefox_driver_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                     'drivers', 'firefox')
  pkgdriver = api.cipd.EnsureFile()
  pkgdriver.add_package('flutter_internal/browser-drivers/firefoxdriver-linux',
                        'latest')
  api.cipd.ensure(firefox_driver_path, pkgdriver)


def DownloadChromeAndDriver(api, chrome_path_84):
  checkout = GetCheckoutPath(api)
  # Download a specific version of chrome-linux before running Flutter Web
  # tests.
  # Please make sure at least one of the versions in this method is this file:
  # flutter/engine/blob/master/lib/web_ui/dev/browser_lock.yaml#L4
  # Chrome uses binary numbers for archiving different versions of the browser.
  chrome_pkg_84 = api.cipd.EnsureFile()
  chrome_pkg_84.add_package('flutter_internal/browsers/chrome/${platform}',
                            'latest-84')
  api.cipd.ensure(chrome_path_84, chrome_pkg_84)
  # Download the driver for Chrome 84.
  chrome_driver_84_path = checkout.join('flutter', 'lib', 'web_ui',
                                        '.dart_tool', 'drivers', 'chrome', '84')
  chrome_pkgdriver_84= api.cipd.EnsureFile()
  chrome_pkgdriver_84.add_package(
      'flutter_internal/browser-drivers/chrome/${platform}', 'latest-84')
  api.cipd.ensure(chrome_driver_84_path, chrome_pkgdriver_84)

  # Chrome uses binary numbers for archiving different versions of the browser.
  # The binary 741412 has major version 82.
  # TODO: remove this version once 84 start working with no issues.
  chrome_path_82 = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                              'chrome', '741412')
  chrome_pkg_82 = api.cipd.EnsureFile()
  chrome_pkg_82.add_package('flutter_internal/browsers/chrome-linux', 'latest')
  api.cipd.ensure(chrome_path_82, chrome_pkg_82)
  # Download the driver for Chrome 82.
  # TODO: remove this version once 84 start working with no issues.
  chrome_driver_82_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                     'drivers', 'chrome')
  chrome_pkgdriver_82 = api.cipd.EnsureFile()
  chrome_pkgdriver_82.add_package(
      'flutter_internal/browser-drivers/chromedriver-linux', 'latest')
  api.cipd.ensure(chrome_driver_82_path, chrome_pkgdriver_82)

def CloneGoldens(api):
  builder_root = api.path['cache'].join('builder')
  goldens = builder_root.join('goldens')
  api.file.ensure_directory('mkdir goldens', goldens)
  checkout = GetCheckoutPath(api)
  golden_yaml_file = checkout.join('flutter', 'lib', 'web_ui', 'dev',
                                   'goldens_lock.yaml')
  with api.context(cwd=builder_root):
    # Use golden_lock.yaml file to read url of the goldens repository and
    # the revision number to checkout.
    # https://github.com/flutter/engine/blob/master/lib/web_ui/dev/goldens_lock.yaml
    # This file is used by web engine developers. The engine developers update
    # the flutter/goldens.git repo when they  need changes. Later change the
    # revision number on this file.
    result = api.yaml.read(
        'read yaml',
        golden_yaml_file,
        api.json.output(),
    )
    # The content of the file is expected to be:
    #
    # repository: https://github.com/flutter/goldens.git
    # revision: b6efc75885c23f0b5c485d8bd659ed339feec9ec
    golden_lock_content = result.json.output
    repo = golden_lock_content['repository']
    revision_number = golden_lock_content['revision']
  with api.context(cwd=goldens):
    api.git.checkout(
      repo,
      dir_path=goldens,
      ref=revision_number,
      recursive=True,
      set_got_revision=True
    )
  golden_files = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                               'goldens')
  api.file.copytree('copy goldens', goldens, golden_files)

def UploadFailingGoldens(api, checkout):
    logs_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                              'test_results')
    tests_info_file_path = logs_path.join('info.txt')
    api.file.write_text('write info file',
                        tests_info_file_path,
                        'tests for %s' % api.platform.name,
                        'tests for windows',
                       )
    if api.properties.get('gcs_goldens_bucket') and not api.runtime.is_experimental:
      api.gsutil.upload(
          bucket=api.properties['gcs_goldens_bucket'],
          source=logs_path,
          dest='%s/%s' % ('web_engine', api.buildbucket.build.id),
          link_name='archive goldens',
          args=['-r'],
          multithreaded=True,
          name='upload goldens %s' % api.buildbucket.build.id,
          unauthenticated_url=True)
      html_files = api.file.glob_paths(
         'html goldens',
         source=logs_path,
         pattern='*.html',
         test_data=('a.html',)).get_result()
      with api.step.nest('Failed golden links') as presentation:
        for html_file in html_files:
          base_name = api.path.basename(html_file)
          url = 'https://storage.googleapis.com/%s/web_engine/%s/%s' % (
              api.properties['gcs_goldens_bucket'],
              api.buildbucket.build.id, base_name)
          presentation.links[base_name] = url

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
  dart_bin = checkout.join('third_party', 'dart', 'tools', 'sdks', 'dart-sdk',
                           'bin')

  android_home = checkout.join('third_party', 'android_tools', 'sdk')

  env = {
      'GOMA_DIR': api.goma.goma_dir,
      'ANDROID_HOME': str(android_home),
      'CHROME_NO_SANDBOX': 'true',
      'ENGINE_PATH': cache_root
  }
  env_prefixes = {'PATH': [dart_bin]}

  # Checkout source code and build
  api.repo_util.engine_checkout(cache_root, env, env_prefixes)

  if api.platform.is_mac:
    CloneGoldens(api)

  with api.context(
      cwd=cache_root, env=env,
      env_prefixes=env_prefixes), api.depot_tools.on_path():

    # Checks before building the engine. Only run on Linux.
    if api.platform.is_linux:
      api.json_util.validate_json(checkout.join('flutter', 'ci'))
      FormatAndDartTest(api)
      Lint(api)

    # Presence of tags in git repo is critical for determining dart version.
    dart_sdk_dir = GetCheckoutPath(api).join('third_party', 'dart')
    with api.context(cwd=dart_sdk_dir):
      # The default fetch remote is a local dir, so explicitly fetch from
      # upstream remote
      api.step('Fetch dart tags',
              ['git', 'fetch', 'https://dart.googlesource.com/sdk.git', '--tags'])
      api.step('List all tags', ['git', 'tag', '--list'])

    api.gclient.runhooks()

    target_name = 'host_debug_unopt'
    gn_flags = ['--unoptimized', '--full-dart-sdk']
    # Mac needs to install xcode as part of the building process.
    additional_args = []
    felt_cmd = [
        checkout.join('out', target_name, 'dart-sdk', 'bin', 'dart'),
        'dev/felt.dart'
    ]

    if api.platform.is_mac:
      with SetupXcode(api):
        RunGN(api, *gn_flags)
        Build(api, target_name)
        additional_args = ['--browser', 'ios-safari']
    else:
      RunGN(api, *gn_flags)
      Build(api, target_name)
      if api.platform.is_win:
        felt_cmd = [
            checkout.join('flutter', 'lib', 'web_ui', 'dev', 'felt_windows.bat')
        ]
    # Update dart packages and run tests.
    local_pub = checkout.join('out', target_name, 'dart-sdk', 'bin', 'pub')
    with api.context(
        cwd=checkout.join('flutter', 'web_sdk', 'web_engine_tester')):
      api.step('pub get in web_engine_tester', [local_pub, 'get'])
    with api.context(cwd=checkout.join('flutter', 'lib', 'web_ui')):
      api.step('pub get in web_engine_tester', [local_pub, 'get'])
      felt_licenses = copy.deepcopy(felt_cmd)
      felt_licenses.append('check-licenses')
      api.step('felt licenses', felt_licenses)
      if api.platform.is_win:
        chrome_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                       'chrome', '768975')
      if api.platform.is_mac:
        chrome_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                       'chrome', '768985')
        additional_args_safari_desktop = ['--browser', 'safari']
        felt_test_safari_desktop = copy.deepcopy(felt_cmd)
        felt_test_safari_desktop.append('test')
        felt_test_safari_desktop.extend(additional_args_safari_desktop)
        api.step('felt test safari desktop', felt_test_safari_desktop)
      if api.platform.is_linux:
        web_engine_analysis_cmd = [
            checkout.join('flutter', 'lib', 'web_ui', 'dev',
                          'web_engine_analysis.sh'),
        ]
        api.step('web engine analysis', web_engine_analysis_cmd)
        DownloadFirefoxDriver(api)
        additional_args_firefox = ['--browser', 'firefox']
        felt_test_firefox = copy.deepcopy(felt_cmd)
        felt_test_firefox.append('test')
        felt_test_firefox.extend(additional_args_firefox)
        api.step('felt test firefox', felt_test_firefox)
        chrome_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                       'chrome', '768968')
      DownloadChromeAndDriver(api, chrome_path)
      felt_test = copy.deepcopy(felt_cmd)
      felt_test.append('test')
      felt_test.extend(additional_args)
      if api.platform.is_mac:
          with SetupXcode(api):
            with recipe_api.defer_results():
              api.step('felt ios-safari test',felt_test)
              UploadFailingGoldens(api, checkout)
      else:
        with recipe_api.defer_results():
          api.step('felt test chrome', felt_test)
          UploadFailingGoldens(api, checkout)

  # Collect memory/cpu/process after task execution.
  api.os_utils.collect_os_info()

def GenTests(api):
  golden_yaml_file = {'repository': 'repo', 'revision': 'b6efc758'}
  yield api.test('linux-post-submit') + api.properties(
      goma_jobs='200') + api.platform('linux', 64)
  yield api.test('windows-post-submit') + api.properties(
      goma_jobs='200') + api.platform('win', 32)
  yield api.test('mac-post-submit',
      api.step_data('read yaml.parse', api.json.output(golden_yaml_file)),
      api.properties(goma_jobs='200'), api.platform('mac', 64))
  yield api.test('linux-pre-submit') + api.properties(
      goma_jobs='200',
      git_url='https://mygitrepo',
      git_ref='refs/pull/1/head',
      gcs_goldens_bucket='mybucket',
      clobber=True) + api.platform('linux', 64)
