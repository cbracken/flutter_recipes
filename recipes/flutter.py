# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
import re

DEPS = [
    'depot_tools/depot_tools',
    'depot_tools/git',
    'depot_tools/gsutil',
    'depot_tools/osx_sdk',
    'depot_tools/windows_sdk',
    'flutter/zip',
    'recipe_engine/buildbucket',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/isolated',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/raw_io',
    'recipe_engine/runtime',
    'recipe_engine/step',
    'recipe_engine/swarming',
    'recipe_engine/url',
]

BUCKET_NAME = 'flutter_infra'
PACKAGED_REF_RE = re.compile(r'^refs/heads/(dev|beta|stable)$')

# Fuchsia globals.
FUCHSIA_IMAGE_NAME = 'generic-x64.tgz'
FUCHSIA_PACKAGES_ARCHIVE_NAME = 'generic-x64.tar.gz'
FUCHSIA_TEST_SCRIPT_NAME = 'run_fuchsia_tests.sh'


@contextmanager
def _PlatformSDK(api):
  if api.platform.is_win:
    with api.windows_sdk():
      with InstallOpenJDK(api):
        yield
  elif api.platform.is_mac:
    yield
  elif api.platform.is_linux:
    with InstallOpenJDK(api):
      yield


@contextmanager
def Install7za(api):
  if api.platform.is_win:
    sevenzip_cache_dir = api.path['cache'].join('builder', '7za')
    api.cipd.ensure(
        sevenzip_cache_dir,
        api.cipd.EnsureFile().add_package(
            'flutter_internal/tools/7za/${platform}', 'version:19.00'))
    with api.context(env_prefixes={'PATH': [sevenzip_cache_dir]}):
      yield
  else:
    yield


def EnsureGoldctl(api):
  with api.step.nest('Download goldctl'):
    goldctl_cache_dir = api.path['cache'].join('gold')
    api.cipd.ensure(
        goldctl_cache_dir,
        api.cipd.EnsureFile().add_package('skia/tools/goldctl/${platform}',
                                          'latest'))
    return goldctl_cache_dir.join('goldctl')


def ShouldRunGoldTryjob(api):
  """Specifies pre-submit conditions for executing gold tryjobs."""
  return api.properties.get('gold_tryjob', True)


@contextmanager
def MakeTempDir(api, label):
  temp_dir = api.path.mkdtemp('tmp')
  try:
    yield temp_dir
  finally:
    api.file.rmtree('temp dir for %s' % label, temp_dir)


def DownloadFuchsiaSystemImageAndPackages(api, fuchsia_dir, target_dir):
  with api.step.nest('Download Fuchsia Archives'):
    manifest_path = fuchsia_dir.join('meta', 'manifest.json')
    manifest_data = api.file.read_json(
        'Read fuchsia build manifest', manifest_path, test_data={'id': 123})
    build_id = manifest_data['id']
    bucket_name = 'fuchsia'
    api.gsutil.download(
        bucket_name,
        'development/%s/images/%s' % (build_id, FUCHSIA_IMAGE_NAME),
        target_dir,
        name="download fuchsia system image")
    api.gsutil.download(
        bucket_name,
        'development/%s/packages/%s' %
        (build_id, FUCHSIA_PACKAGES_ARCHIVE_NAME),
        target_dir,
        name="download fuchsia companion packages")


def IsolateFuchsiaCtlDeps(api, fuchsia_ctl_wd):
  checkout = api.path['checkout']
  flutter_bin = checkout.join('bin')
  fuchsia_dir = flutter_bin.join('cache', 'artifacts', 'fuchsia')
  fuchsia_tools = fuchsia_dir.join('tools')
  DownloadFuchsiaSystemImageAndPackages(api, fuchsia_dir, fuchsia_ctl_wd)
  with api.step.nest('Copy Fuchsia CTL Deps'):
    api.file.copy('Copy test script',
                  checkout.join('dev', 'bots', FUCHSIA_TEST_SCRIPT_NAME),
                  fuchsia_ctl_wd)
    api.file.copy('Copy dev_finder', fuchsia_tools.join('dev_finder'),
                  fuchsia_ctl_wd)
    api.file.copy('Copy pm', fuchsia_tools.join('pm'), fuchsia_ctl_wd)


def CollectFlutterDriverTestResults(api, fuchsia_swarming_metadata):
  # Collect the result of the task by metadata.
  links = {m.id: m.task_ui_link for m in fuchsia_swarming_metadata}
  fuchsia_output = api.path['cleanup'].join('fuchsia_test_output')
  api.file.ensure_directory('swarming output', fuchsia_output)
  results = api.swarming.collect(
      'collect',
      fuchsia_swarming_metadata,
      output_dir=fuchsia_output,
      timeout='30m')
  ProcessResults(api, results, links)


def ProcessResults(api, results, links):
  with api.step.defer_results():
    for result in results:
      with api.step.nest('Result for %s' % result.name) as presentation:
        if (result.state is None or
            result.state != api.swarming.TaskState.COMPLETED):
          presentation.status = api.step.EXCEPTION
        elif not result.success:
          presentation.status = api.step.FAILURE
        presentation.links['task UI'] = links[result.id]


def IsolateDriverDeps(api):
  checkout = api.path['checkout']
  with api.step.nest('Create Isolate Archive'):
    with MakeTempDir(api, 'isolate_dir') as isolate_dir:
      IsolateFuchsiaCtlDeps(api, isolate_dir)
      isolated_flutter = isolate_dir.join('flutter')
      api.file.copytree('Copy flutter framework', checkout, isolated_flutter)
      isolated = api.isolated.isolated(isolate_dir)
      isolated.add_dir(isolate_dir)
      return isolated.archive('Archive Fuchsia Test Isolate')


def SwarmFuchsiaTests(api):
  isolated_hash = IsolateDriverDeps(api)
  fuchsia_ctl_package = api.cipd.EnsureFile()
  fuchsia_ctl_package.add_package('flutter/fuchsia_ctl/${platform}',
                                  api.properties.get('fuchsia_ctl_version'))
  request = (
      api.swarming.task_request().with_name(
          'flutter_fuchsia_driver_tests').with_priority(100))
  request = (
      request.with_slice(
          0,
          request[0].with_cipd_ensure_file(fuchsia_ctl_package).with_command([
              './%s' % FUCHSIA_TEST_SCRIPT_NAME, FUCHSIA_IMAGE_NAME
          ]).with_dimensions(pool='luci.flutter.tests').with_isolated(
              isolated_hash).with_expiration_secs(3600).with_io_timeout_secs(
                  3600).with_execution_timeout_secs(3600).with_idempotent(
                      True).with_containment_type('AUTO')))

  return api.swarming.trigger(
      'Trigger Fuchsia Driver Tests', requests=[request])


def RunFuchsiaDriverTests(api):
  # Fuchsia driver tests are currently only run from linux hosts.
  if not api.platform.is_linux:
    return
  with api.step.nest('Run Fuchsia Driver Tests'):
    flutter_executable = 'flutter' if not api.platform.is_win else 'flutter.bat'
    api.step('precache fuchsia artifacts', [
        flutter_executable, 'precache', '--fuchsia', '--no-android', '--no-ios'
    ])
    api.step('precache flutter runners', [
        flutter_executable, 'precache', '--flutter_runner', '--no-android',
        '--no-ios'
    ])
    return SwarmFuchsiaTests(api)


def InstallOpenJDK(api):
  java_cache_dir = api.path['cache'].join('java')
  api.cipd.ensure(
      java_cache_dir,
      api.cipd.EnsureFile().add_package(
          'flutter_internal/java/openjdk/${platform}', 'version:1.8.0u202-b08'))
  return api.context(
      env={'JAVA_HOME': java_cache_dir},
      env_prefixes={'PATH': [java_cache_dir.join('bin')]})


def EnsureCloudKMS(api, version=None):
  with api.step.nest('ensure_cloudkms'):
    with api.context(infra_steps=True):
      pkgs = api.cipd.EnsureFile()
      pkgs.add_package('infra/tools/luci/cloudkms/${platform}', version or
                       'latest')
      cipd_dir = api.path['start_dir'].join('cipd', 'cloudkms')
      api.cipd.ensure(cipd_dir, pkgs)
      return cipd_dir.join('cloudkms')


def DecryptKMS(api, step_name, crypto_key_path, ciphertext_file,
               plaintext_file):
  kms_path = EnsureCloudKMS(api)
  return api.step(step_name, [
      kms_path,
      'decrypt',
      '-input',
      ciphertext_file,
      '-output',
      plaintext_file,
      crypto_key_path,
  ])


def GetCloudPath(api, git_hash, path):
  if api.runtime.is_experimental:
    return 'flutter/experimental/%s/%s' % (git_hash, path)
  return 'flutter/%s/%s' % (git_hash, path)


def UploadFlutterCoverage(api):
  """Uploads the Flutter coverage output to cloud storage and Coveralls.
  """
  if not api.properties.get('upload_packages', False):
    return

  # Upload latest coverage to cloud storage.
  checkout = api.path['checkout']
  flutter_package_dir = checkout.join('packages', 'flutter')
  coverage_path = flutter_package_dir.join('coverage', 'lcov.info')
  api.gsutil.upload(
      coverage_path,
      BUCKET_NAME,
      GetCloudPath(api, 'coverage', 'lcov.info'),
      link_name='lcov.info',
      name='upload coverage data')

  token_path = flutter_package_dir.join('.coveralls.yml')
  DecryptKMS(api, 'decrypt coveralls token',
          'projects/flutter-infra/locations/global' \
          '/keyRings/luci/cryptoKeys/coveralls',
          api.resource('coveralls-token.enc'),
          token_path)
  pub_executable = 'pub' if not api.platform.is_win else 'pub.exe'
  api.step('pub global activate coveralls', [
      pub_executable, 'global', 'activate', 'coveralls', '5.1.0',
      '--no-executables'
  ])
  with api.context(cwd=flutter_package_dir):
    api.step('upload to coveralls',
             [pub_executable, 'global', 'run', 'coveralls:main', coverage_path])


def CreateAndUploadFlutterPackage(api, git_hash, branch):
  """Prepares, builds, and uploads an all-inclusive archive package."""
  # For creating the packages, we need to have the master branch version of the
  # script, but we need to know what the revision in git_hash is first. So, we
  # end up checking out the flutter repo twice: once on the branch we're going
  # to package, to find out the hash to use, and again here so that we have the
  # current version of the packaging script.
  api.git.checkout(
      'https://chromium.googlesource.com/external/github.com/flutter/flutter',
      ref='master',
      recursive=True,
      set_got_revision=True)

  flutter_executable = 'flutter' if not api.platform.is_win else 'flutter.bat'
  dart_executable = 'dart' if not api.platform.is_win else 'dart.exe'
  work_dir = api.path['start_dir'].join('archive')
  prepare_script = api.path['checkout'].join('dev', 'bots',
                                             'prepare_package.dart')
  api.step('flutter doctor', [flutter_executable, 'doctor'])
  api.step('download dependencies', [flutter_executable, 'update-packages'])
  api.file.rmtree('clean archive work directory', work_dir)
  api.file.ensure_directory('(re)create archive work directory', work_dir)
  with Install7za(api):
    with api.context(cwd=api.path['start_dir']):
      step_args = [
          dart_executable, prepare_script,
          '--temp_dir=%s' % work_dir,
          '--revision=%s' % git_hash,
          '--branch=%s' % branch
      ]
      if not api.runtime.is_experimental:
        step_args.append('--publish')
      api.step('prepare, create and publish a flutter archive', step_args)


def RunSteps(api):
  git_url = \
    'https://chromium.googlesource.com/external/github.com/flutter/flutter'
  git_ref = api.buildbucket.gitiles_commit.ref
  if ('git_url' in api.properties and 'git_ref' in api.properties):
    git_url = api.properties['git_url']
    git_ref = api.properties['git_ref']

  git_hash = api.git.checkout(
      git_url, ref=git_ref, recursive=True, set_got_revision=True, tags=True)
  checkout = api.path['checkout']

  dart_bin = checkout.join('bin', 'cache', 'dart-sdk', 'bin')
  flutter_bin = checkout.join('bin')

  path_prefixes = [
      flutter_bin,
      dart_bin,
  ]

  env_prefixes = {'PATH': path_prefixes}

  # TODO(eseidel): This is named exactly '.pub-cache' as a hack around
  # a regexp in flutter_tools analyze.dart which is in turn a hack around:
  # https://github.com/dart-lang/sdk/issues/25722
  pub_cache = checkout.join('.pub-cache')
  env = {
      # Setup our own pub_cache to not affect other slaves on this machine,
      # and so that the pre-populated pub cache is contained in the package.
      'PUB_CACHE': pub_cache,
      # Windows Packaging script assumes this is set.
      'DEPOT_TOOLS': str(api.depot_tools.root),
      # Goldctl binary for Flutter Gold, used by framework and driver tests.
      'GOLDCTL': EnsureGoldctl(api),
  }

  if ShouldRunGoldTryjob(api) and git_ref:
    # Tryjob should be run for given git_ref
    env.update({
        'GOLD_TRYJOB': git_ref,
    })

  flutter_executable = 'flutter' if not api.platform.is_win else 'flutter.bat'
  dart_executable = 'dart' if not api.platform.is_win else 'dart.exe'

  with api.context(env=env, env_prefixes=env_prefixes):
    with api.depot_tools.on_path():
      if git_ref:
        match = PACKAGED_REF_RE.match(git_ref)
        if match:
          branch = match.group(1)
          CreateAndUploadFlutterPackage(api, git_hash, branch)
          # Nothing left to do on a packaging branch.
          return

  # The context adds dart-sdk tools to PATH and sets PUB_CACHE.
  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout):
    api.step('flutter doctor', [flutter_executable, 'doctor'])
    api.step('download dependencies', [flutter_executable, 'update-packages'])

  # TODO (kaushikiska): Should we only run the tests on specific shard types?
  fuchsia_swarming_metadata = None
  with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout):
    fuchsia_swarming_metadata = RunFuchsiaDriverTests(api)

  with _PlatformSDK(api):
    with api.context(env=env, env_prefixes=env_prefixes, cwd=checkout):
      shard = api.properties['shard']
      shard_env = env
      shard_env['SHARD'] = shard
      with api.context(env=shard_env):
        api.step('run test.dart for %s shard' % shard,
                 [dart_executable,
                  checkout.join('dev', 'bots', 'test.dart')])
      if fuchsia_swarming_metadata:
        CollectFlutterDriverTestResults(api, fuchsia_swarming_metadata)
      if shard == 'coverage':
        UploadFlutterCoverage(api)
      # Windows uses exclusive file locking.  On LUCI, if these processes remain
      # they will cause the build to fail because the builder won't be able to
      # clean up.
      # This might fail if there's not actually a process running, which is
      # fine.
      # If it actually fails to kill the task, the job will just fail anyway.
      if api.platform.is_win:

        def KillAll(name, exe_name):
          api.step(
              name, ['taskkill', '/f', '/im', exe_name, '/t'], ok_ret='any')

        KillAll('stop gradle daemon', 'java.exe')
        KillAll('stop dart', 'dart.exe')
        KillAll('stop adb', 'adb.exe')


def GenTests(api):
  for experimental in (True, False):
    for should_upload in (True, False):
      yield (api.test(
          'linux_master_coverage_%s%s' %
          ('_experimental' if experimental else '',
           '_upload' if should_upload else ''),
          api.runtime(is_luci=True, is_experimental=experimental),
          api.properties(
              shard='coverage',
              coveralls_lcov_version='5.1.0',
              upload_packages=should_upload,
              gold_tryjob=not should_upload),
      ) + api.post_check(lambda check, steps: check('Download goldctl' in steps)
                        ))
      for platform in ('mac', 'linux', 'win'):
        for branch in ('master', 'dev', 'beta', 'stable'):
          git_ref = 'refs/heads/' + branch
          test = api.test(
              '%s_%s%s%s' %
              (platform, branch, '_experimental' if experimental else '',
               '_upload' if should_upload else ''),
              api.platform(platform, 64),
              api.buildbucket.ci_build(git_ref=git_ref, revision=None),
              api.properties(
                  shard='tests',
                  fuchsia_ctl_version='version:0.0.2',
                  upload_packages=should_upload,
                  gold_tryjob=not should_upload),
              api.runtime(is_luci=True, is_experimental=experimental),
          )
          yield test + api.post_check(lambda check, steps: check(
              'Download goldctl' in steps))

  yield (api.test(
      'pull_request',
      api.runtime(is_luci=True, is_experimental=True),
      api.properties(
          git_url='https://github.com/flutter/flutter',
          git_ref='refs/pull/1/head',
          shard='tests',
          fuchsia_ctl_version='version:0.0.2',
          should_upload=False),
  ) + api.post_check(lambda check, steps: check('Download goldctl' in steps)))

  yield (
      api.test(
          'Linux Fuchsia Infra Failure', api.platform('linux', 64),
          api.buildbucket.ci_build(git_ref='refs/head/master', revision=None),
          api.step_data('Run Fuchsia Driver Tests.Trigger Fuchsia Driver Tests',
                        api.swarming.trigger(['task1', 'task2'])),
          api.step_data(
              'collect',
              api.swarming.collect([
                  api.swarming.task_result(0, 'task1', state=None),
                  api.swarming.task_result(1, 'task1', failure=True)
              ])),
          api.properties(
              shard='tests',
              fuchsia_ctl_version='version:0.0.2',
              upload_packages=True,
              gold_tryjob=False),
          api.runtime(is_luci=True, is_experimental=False)) +
      api.post_check(lambda check, steps: check('Download goldctl' in steps)))
