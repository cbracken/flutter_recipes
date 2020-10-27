# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
import re

DEPS = [
    'depot_tools/depot_tools',
    'depot_tools/git',
    'flutter/json_util',
    'flutter/repo_util',
    'recipe_engine/buildbucket',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/runtime',
    'recipe_engine/step',
]

PACKAGED_REF_RE = re.compile(r'^refs/heads/(dev|beta|stable)$')


@contextmanager
def Install7za(api):
  if api.platform.is_win:
    sevenzip_cache_dir = api.path['cache'].join('builder', '7za')
    api.cipd.ensure(
        sevenzip_cache_dir,
        api.cipd.EnsureFile().add_package(
            'flutter_internal/tools/7za/${platform}', 'version:19.00'
        )
    )
    with api.context(env_prefixes={'PATH': [sevenzip_cache_dir]}):
      yield
  else:
    yield


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
      set_got_revision=True
  )

  flutter_executable = 'flutter' if not api.platform.is_win else 'flutter.bat'
  dart_executable = 'dart' if not api.platform.is_win else 'dart.exe'
  work_dir = api.path['start_dir'].join('archive')
  prepare_script = api.path['checkout'].join(
      'dev', 'bots', 'prepare_package.dart'
  )
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
  git_ref = api.properties.get('git_ref') or api.buildbucket.gitiles_commit.ref
  assert git_ref
  checkout_path = api.path['start_dir'].join('flutter')
  with api.step.nest('checkout source code'):
    api.repo_util.checkout(
        'flutter',
        checkout_path=checkout_path,
        url=api.properties.get('git_url'),
        ref=api.properties.get('git_ref')
    )
  env, env_prefixes = api.repo_util.flutter_environment(checkout_path)
  git_url = \
    'https://chromium.googlesource.com/external/github.com/flutter/flutter'
  git_url = api.properties.get('git_url') or git_url
  git_hash = api.git.checkout(
      git_url, ref=git_ref, recursive=True, set_got_revision=True, tags=True
  )
  with api.context(env=env, env_prefixes=env_prefixes):
    with api.depot_tools.on_path():
      if git_ref:
        match = PACKAGED_REF_RE.match(git_ref)
        if match:
          branch = match.group(1)
          CreateAndUploadFlutterPackage(api, git_hash, branch)
          # Nothing left to do on a packaging branch.
          return


def GenTests(api):
  for experimental in (True, False):
    for should_upload in (True, False):
      for platform in ('mac', 'linux', 'win'):
        for branch in ('master', 'dev', 'beta', 'stable'):
          git_ref = 'refs/heads/' + branch
          test = api.test(
              '%s_%s%s%s' % (
                  platform, branch, '_experimental' if experimental else '',
                  '_upload' if should_upload else ''
              ), api.platform(platform, 64),
              api.buildbucket.ci_build(git_ref=git_ref, revision=None),
              api.properties(
                  shard='tests',
                  fuchsia_ctl_version='version:0.0.2',
                  upload_packages=should_upload,
                  gold_tryjob=not should_upload
              ), api.runtime(is_experimental=experimental),
              api.repo_util.flutter_environment_data()
          )
          yield test
