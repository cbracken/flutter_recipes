# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Recipe for cocoon repository tests."""

DEPS = [
    'depot_tools/git',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/runtime',
    'recipe_engine/step',
    'yaml',
]


def RunSteps(api):
  """Steps to checkout cocoon, dependencies and execute tests."""
  # Checkout cocoon.
  cocoon_git_url = 'https://github.com/flutter/cocoon'
  cocoon_git_ref = api.buildbucket.gitiles_commit.ref
  if 'git_ref' in api.properties:
    cocoon_git_ref = api.properties['git_ref']

  api.git.checkout(
      cocoon_git_url,
      ref=cocoon_git_ref,
      recursive=True,
      set_got_revision=True,
      tags=True)

  # Checkout flutter/flutter at head.
  flutter_git_url = \
    'https://chromium.googlesource.com/external/github.com/flutter/flutter'
  flutter_git_ref = 'refs/heads/stable'
  api.git.checkout(
      flutter_git_url,
      ref=flutter_git_ref,
      recursive=True,
      set_got_revision=True,
      tags=True)

  # Run tests
  start_path = api.path['start_dir']
  cocoon_path = start_path.join('cocoon')
  flutter_path = start_path.join('flutter')
  dart_bin = flutter_path.join('bin', 'cache', 'dart-sdk', 'bin')
  flutter_bin = flutter_path.join('bin')

  path_prefixes = [
      flutter_bin,
      dart_bin,
  ]

  env_prefixes = {'PATH': path_prefixes}

  pub_cache = api.path['cache'].join('.pub-cache')
  env = {
      # Setup our own pub_cache to not affect other bots on this machine,
      # and so that the pre-populated pub cache is contained in the package.
      'PUB_CACHE': pub_cache,
  }

  # Read yaml file
  tests_yaml_path = start_path.join('cocoon', 'tests.yaml')
  result = api.yaml.read('read yaml', tests_yaml_path, api.json.output())

  # The context adds dart-sdk tools to PATH and sets PUB_CACHE.
  with api.context(env=env, env_prefixes=env_prefixes, cwd=start_path):
    api.step('flutter doctor', cmd=['flutter', 'doctor'])
    prepare_script_path = cocoon_path.join(
        'test_utilities', 'bin', 'prepare_environment.sh')
    api.step('prepare environment', cmd=['bash', prepare_script_path])
    for task in result.json.output['tasks']:
      script_path = cocoon_path.join(task['script'])
      test_folder = cocoon_path.join(task['task'])
      api.step(task['task'], cmd=['bash', script_path, test_folder])


def GenTests(api):
  tasks_dict = {'tasks': [{'task': 'one', 'script': 'myscript'}]}
  yield (
      api.test(
          'pull_request',
          api.runtime(is_luci=True, is_experimental=True),
          api.properties(
              git_url='https://github.com/flutter/cocoon',
              git_ref='refs/pull/1/head'),) +
      api.step_data('read yaml.parse', api.json.output(tasks_dict))
  )
