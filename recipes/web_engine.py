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
    'build/goma',
    'depot_tools/gclient',
    'depot_tools/gsutil',
    'recipe_engine/cipd',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/context',
    'depot_tools/depot_tools',
    'recipe_engine/buildbucket',
    'depot_tools/osx_sdk',
    'recipe_engine/properties',
    'recipe_engine/platform',
    'recipe_engine/step',
    'depot_tools/bot_update',
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


def GetCheckout(api):
  git_url = GIT_REPO
  git_id = api.buildbucket.gitiles_commit.id
  git_ref = api.buildbucket.gitiles_commit.ref
  if 'git_url' in api.properties and 'git_ref' in api.properties:
    git_url = api.properties['git_url']
    git_id = api.properties['git_ref']
    git_ref = api.properties['git_ref']

  src_cfg = api.gclient.make_config()
  soln = src_cfg.solutions.add()
  soln.name = 'src/flutter'
  soln.url = git_url
  soln.revision = git_id
  src_cfg.parent_got_revision_mapping['parent_got_revision'] = 'got_revision'
  src_cfg.repo_path_map[git_url] = ('src/flutter', git_ref)
  api.gclient.c = src_cfg
  api.gclient.c.got_revision_mapping['src/flutter'] = 'got_engine_revision'
  api.bot_update.ensure_checkout()
  api.gclient.runhooks()


def Build(api, config, *targets):
  checkout = GetCheckoutPath(api)
  build_dir = checkout.join('out/%s' % config)
  goma_jobs = api.properties['goma_jobs']
  ninja_args = [api.depot_tools.ninja_path, '-j', goma_jobs, '-C', build_dir]
  ninja_args.extend(targets)
  api.goma.build_with_goma(
      name='build %s' % ' '.join([config] + list(targets)),
      ninja_command=ninja_args)


def RunGN(api, *args):
  checkout = GetCheckoutPath(api)
  gn_cmd = ['python', checkout.join('flutter/tools/gn'), '--goma']
  gn_cmd.extend(args)
  api.step('gn %s' % ' '.join(args), gn_cmd)


def GetCheckoutPath(api):
  return api.path['cache'].join('builder', 'src')


def DownloadChromeAndDriver(api):
  checkout = GetCheckoutPath(api)
  # Download a specific version of chrome-linux before running Flutter Web
  # tests.
  # Chrome uses binary numbers for archiving different versions of the browser.
  # The binary 741412 has major version 82. It is tested in both headless and
  # no-headless mode of Chrome Driver for integration tests.
  # Please make sure to also change the following lock file when updating the
  # recipe:
  # flutter/engine/blob/master/lib/web_ui/dev/browser_lock.yaml#L4
  chrome_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                              'chrome', '741412')
  pkgs = api.cipd.EnsureFile()
  pkgs.add_package('flutter_internal/browsers/chrome-linux', 'latest')
  api.cipd.ensure(chrome_path, pkgs)
  # Download the driver fort the same version of chrome-linux.
  chrome_driver_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                     'drivers', 'chrome')
  pkgdriver = api.cipd.EnsureFile()
  pkgdriver.add_package('flutter_internal/browser-drivers/chromedriver-linux',
                        'latest')
  api.cipd.ensure(chrome_driver_path, pkgdriver)


def RunSteps(api, properties, env_properties):
  """Steps to checkout flutter engine and execute web tests."""
  cache_root = api.path['cache'].join('builder')
  checkout = GetCheckoutPath(api)

  if properties.clobber:
    api.file.rmtree('Clobber cache', cache_root)
  api.file.rmtree('Clobber build output', checkout.join('out'))

  api.file.ensure_directory('Ensure checkout cache', cache_root)
  api.goma.ensure_goma()
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

  with api.context(
      cwd=cache_root, env=env,
      env_prefixes=env_prefixes), api.depot_tools.on_path():
    # Checkout source code and build
    GetCheckout(api)
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
        additional_args = ['--browser', 'safari']
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
      if api.platform.is_linux:
        additional_args_firefox = ['--browser', 'firefox']
        felt_test_firefox = copy.deepcopy(felt_cmd)
        felt_test_firefox.append('test')
        felt_test_firefox.extend(additional_args_firefox)
        api.step('felt test firefox', felt_test_firefox)
        DownloadChromeAndDriver(api)
      felt_test = copy.deepcopy(felt_cmd)
      felt_test.append('test')
      felt_test.extend(additional_args)
      with recipe_api.defer_results():
        if not api.platform.is_mac:
          api.step('felt test chrome', felt_test)
          logs_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                    'test_results')
          if api.properties.get('gcs_goldens_bucket'):
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

        else:
          api.step('kill safari', ['pkill', '-lf', 'Safari'])
          api.step('felt test safari', felt_test)
          api.step('kill safari', ['pkill', '-lf', 'Safari'])

def GenTests(api):
  yield api.test('linux-post-submit') + api.properties(
      goma_jobs='200') + api.platform('linux', 64)
  yield api.test('windows-post-submit') + api.properties(
      goma_jobs='200') + api.platform('win', 32)
  yield api.test('mac-post-submit') + api.properties(
      goma_jobs='200') + api.platform('mac', 64)
  yield api.test('linux-pre-submit') + api.properties(
      goma_jobs='200',
      git_url='https://mygitrepo',
      git_ref='refs/pull/1/head',
      gcs_goldens_bucket='mybucket',
      clobber=True) + api.platform('linux', 64)
