# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager

from PB.recipes.flutter.engine import InputProperties
from PB.recipes.flutter.engine import EnvProperties

from PB.go.chromium.org.luci.buildbucket.proto import build as build_pb2
from google.protobuf import struct_pb2

DEPS = [
    'fuchsia/gcloud',
    'fuchsia/goma',
    'depot_tools/depot_tools',
    'depot_tools/gclient',
    'depot_tools/git',
    'depot_tools/gsutil',
    'flutter/bucket_util',
    'flutter/os_utils',
    'flutter/repo_util',
    'flutter/zip',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/isolated',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/runtime',
    'recipe_engine/step',
]

# Account for ~1 hour queue time when there is a high number of commits.
DRONE_TIMEOUT_SECS = 7200

BUCKET_NAME = 'flutter_infra'
MAVEN_BUCKET_NAME = 'download.flutter.io'
ICU_DATA_PATH = 'third_party/icu/flutter/icudtl.dat'
GIT_REPO = (
    'https://chromium.googlesource.com/external/github.com/flutter/engine')

PROPERTIES = InputProperties
ENV_PROPERTIES = EnvProperties


def GetCheckoutPath(api):
  return api.path['cache'].join('builder', 'src')


def GetGitHash(api):
  with api.context(cwd=GetCheckoutPath(api)):
    return api.step(
        "Retrieve git hash", ["git", "rev-parse", "HEAD"],
        stdout=api.raw_io.output()).stdout.strip()


def GetCloudPath(api, path):
  git_hash = api.buildbucket.gitiles_commit.id
  if api.runtime.is_experimental:
    return 'flutter/experimental/%s/%s' % (git_hash, path)
  return 'flutter/%s/%s' % (git_hash, path)


def Build(api, config, *targets):
  checkout = GetCheckoutPath(api)
  build_dir = checkout.join('out/%s' % config)
  goma_jobs = api.properties['goma_jobs']
  ninja_args = [api.depot_tools.ninja_path, '-j', goma_jobs, '-C', build_dir]
  ninja_args.extend(targets)
  with api.goma.build_with_goma(), api.depot_tools.on_path():
    name = 'build %s' % ' '.join([config] + list(targets))
    api.step(name, ninja_args)


def RunGN(api, *args):
  checkout = GetCheckoutPath(api)
  gn_cmd = ['python', checkout.join('flutter/tools/gn'), '--goma']
  gn_cmd.extend(args)
  api.step('gn %s' % ' '.join(args), gn_cmd)


def NotifyPubsub(api,
                 buildername,
                 bucket,
                 topic='projects/flutter-dashboard/topics/luci-builds-prod'):
  """Sends a pubsub message to the topic specified with buildername and githash, identifying
  the completed build.

  Args:
    api: luci api object.
    buildername(str): The name of builder.
    bucket(str): The name of the bucket.
    topic(str): (optional) gcloud topic to publish message to.
  """
  githash = GetGitHash(api)
  cmd = [
      'pubsub', 'topics', 'publish', topic,
      '--message={"buildername" : "%s", "bucket" : "%s", "githash" : "%s"}' %
      (buildername, bucket, githash)
  ]
  api.gcloud(*cmd)


def UploadArtifacts(api,
                    platform,
                    file_paths=[],
                    directory_paths=[],
                    archive_name='artifacts.zip',
                    pkg_root=None):
  dir_label = '%s UploadArtifacts %s' % (platform, archive_name)
  with api.os_utils.make_temp_directory(dir_label) as temp_dir:
    local_zip = temp_dir.join('artifacts.zip')
    remote_name = '%s/%s' % (platform, archive_name)
    remote_zip = GetCloudPath(api, remote_name)
    if pkg_root is None:
      pkg_root = GetCheckoutPath(api)
    pkg = api.zip.make_package(pkg_root, local_zip)
    api.bucket_util.add_files(pkg, file_paths)
    api.bucket_util.add_directories(pkg, directory_paths)

    pkg.zip('Zip %s %s' % (platform, archive_name))
    if api.bucket_util.should_upload_packages():
      api.bucket_util.safe_upload(local_zip, remote_zip)


def UploadDartSdk(api, archive_name, target_path='src/out/host_debug'):
  api.bucket_util.upload_folder('Upload Dart SDK', target_path, 'dart-sdk',
                                archive_name)

def BuildLinux(api):
  RunGN(api, '--runtime-mode', 'debug', '--full-dart-sdk', '--target-os=linux',
        '--linux-cpu=arm64')
  Build(api, 'linux_debug_arm64')

  RunGN(api, '--runtime-mode', 'debug', '--unoptimized', '--target-os=linux',
        '--linux-cpu=arm64')
  Build(api, 'linux_debug_unopt_arm64')

  RunGN(api, '--runtime-mode', 'profile', '--no-lto', '--target-os=linux',
        '--linux-cpu=arm64')
  Build(api, 'linux_profile_arm64')

  RunGN(api, '--runtime-mode', 'release', '--target-os=linux',
        '--linux-cpu=arm64')
  Build(api, 'linux_release_arm64')

  UploadArtifacts(api, 'linux-arm64', [
      ICU_DATA_PATH,
      'out/linux_debug_arm64/flutter_tester',
      'out/linux_debug_unopt_arm64/gen/flutter/lib/snapshot/isolate_snapshot.bin',
      'out/linux_debug_unopt_arm64/gen/flutter/lib/snapshot/vm_isolate_snapshot.bin',
      'out/linux_debug_unopt_arm64/gen/frontend_server.dart.snapshot',
  ])

  UploadArtifacts(
      api,
      'linux-arm64', [
          'out/linux_release_arm64/font-subset',
          'out/linux_debug_arm64/gen/const_finder.dart.snapshot',
      ],
      archive_name='font-subset.zip'
  )

  UploadDartSdk(
      api,
      archive_name='dart-sdk-linux-arm64.zip',
      target_path='src/out/linux_debug_arm64')


def RunSteps(api, properties, env_properties):
  # Collect memory/cpu/process before task execution.
  api.os_utils.collect_os_info()

  cache_root = api.path['cache'].join('builder')
  checkout = GetCheckoutPath(api)

  api.file.rmtree('Clobber build output', checkout.join('out'))

  api.file.ensure_directory('Ensure checkout cache', cache_root)
  api.goma.ensure()
  dart_bin = checkout.join('third_party', 'dart', 'tools', 'sdks', 'dart-sdk',
                           'bin')

  android_home = checkout.join('third_party', 'android_tools', 'sdk')

  env = {'GOMA_DIR': api.goma.goma_dir, 'ANDROID_HOME': str(android_home)}
  env_prefixes = {}

  api.repo_util.engine_checkout(cache_root, env, env_prefixes)

  # Delete derived data on mac. This is a noop for other platforms.
  api.os_utils.clean_derived_data()

  # Various scripts we run assume access to depot_tools on path for `ninja`.
  with api.context(
      cwd=cache_root, env=env,
      env_prefixes=env_prefixes), api.depot_tools.on_path():

    api.gclient.runhooks()

    if api.platform.is_linux:
      if api.properties.get('build_host', True):
        BuildLinux(api)

    if api.platform.is_mac:
      # no-op
      raise api.step.StepFailure('Mac Arm host builds not supported yet.')
    if api.platform.is_win:
      raise api.step.StepFailure('Windows Arm host builds not supported yet.')

  # Notifies of build completion
  # TODO(crbug.com/843720): replace this when user defined notifications is implemented.
  try:
    NotifyPubsub(api, api.buildbucket.builder_name,
                 api.buildbucket.build.builder.bucket)
  except (api.step.StepFailure) as e:
    pass

  # This is to clean up leaked processes.
  api.os_utils.kill_processes()
  # Collect memory/cpu/process after task execution.
  api.os_utils.collect_os_info()


# pylint: disable=line-too-long
# See https://chromium.googlesource.com/infra/luci/recipes-py/+/refs/heads/master/doc/user_guide.md
# The tests in here make sure that every line of code is used and does not fail.
# pylint: enable=line-too-long
def GenTests(api):
  git_revision = 'abcd1234'
  for platform in ('mac', 'linux', 'win'):
    for should_upload in (True, False):
      test = api.test(
          '%s%s' % (platform, '_upload' if should_upload else ''),
          api.platform(platform, 64),
          api.buildbucket.ci_build(
              builder='%s Engine' % platform.capitalize(),
              git_repo=GIT_REPO,
              project='flutter',
              revision='%s' % git_revision,
          ),
          api.runtime(is_experimental=False),
          api.properties(
              InputProperties(
                  clobber=False,
                  goma_jobs='1024',
                  fuchsia_ctl_version='version:0.0.2',
                  build_host=True,
                  build_fuchsia=True,
                  build_android_aot=True,
                  build_android_debug=True,
                  build_android_vulkan=True,
                  upload_packages=should_upload,
                  force_upload=True,
              ),),
          api.properties.environ(
              EnvProperties(SWARMING_TASK_ID='deadbeef')),
      )
      yield test

  for should_upload in (True, False):
    yield api.test(
        'experimental%s' % ('_upload' if should_upload else ''),
        api.buildbucket.ci_build(
            builder='Linux Engine',
            git_repo=GIT_REPO,
            project='flutter',
        ),
        api.runtime(is_experimental=True),
        api.properties(
            InputProperties(
                goma_jobs='1024',
                fuchsia_ctl_version='version:0.0.2',
                android_sdk_license='android_sdk_hash',
                android_sdk_preview_license='android_sdk_preview_hash',
                upload_packages=should_upload,
            )),
    )
  yield api.test(
      'clobber',
      api.buildbucket.ci_build(
          builder='Linux Host Engine',
          git_repo='https://github.com/flutter/engine',
          project='flutter'),
      api.runtime(is_experimental=True),
      api.properties(
          InputProperties(
              clobber=True,
              git_url='https://github.com/flutter/engine',
              goma_jobs='200',
              git_ref='refs/pull/1/head',
              fuchsia_ctl_version='version:0.0.2',
              build_host=True,
              build_fuchsia=True,
              build_android_aot=True,
              build_android_debug=True,
              build_android_vulkan=True,
              android_sdk_license='android_sdk_hash',
              android_sdk_preview_license='android_sdk_preview_hash')),
  )
  yield api.test(
      'pull_request',
      api.buildbucket.ci_build(
          builder='Linux Host Engine',
          git_repo='https://github.com/flutter/engine',
          project='flutter'),
      api.runtime(is_experimental=True),
      api.properties(
          InputProperties(
              clobber=False,
              git_url='https://github.com/flutter/engine',
              goma_jobs='200',
              git_ref='refs/pull/1/head',
              fuchsia_ctl_version='version:0.0.2',
              build_host=True,
              build_fuchsia=True,
              build_android_aot=True,
              build_android_debug=True,
              build_android_vulkan=True,
              android_sdk_license='android_sdk_hash',
              android_sdk_preview_license='android_sdk_preview_hash')),
  )

  yield api.test(
      'gcloud_pubsub_failure',
      api.buildbucket.ci_build(
          builder='Linux Host Engine',
          git_repo='https://github.com/flutter/engine',
          project='flutter'),
      # Next line force a fail condition for the bot update
      # first execution.
      api.step_data('gcloud pubsub', retcode=1),
      api.runtime(is_experimental=True),
      api.properties(
          InputProperties(
              clobber=False,
              git_url='https://github.com/flutter/engine',
              goma_jobs='200',
              git_ref='refs/pull/1/head',
              fuchsia_ctl_version='version:0.0.2',
              build_host=True,
              build_fuchsia=True,
              build_android_aot=True,
              build_android_debug=True,
              build_android_vulkan=True,
              android_sdk_license='android_sdk_hash',
              android_sdk_preview_license='android_sdk_preview_hash')))
