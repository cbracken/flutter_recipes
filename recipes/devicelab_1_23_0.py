# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine.recipe_api import Property

DEPS = [
    'depot_tools/git',
    'flutter/flutter_deps',
    'flutter/repo_util',
    'flutter/yaml',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
    "flutter/job",
]

PROPERTIES = {
    'role': Property(kind=str, help='either scheduler or worker'),
}


def RunSteps(api, role):
  if role == "scheduler":
    schedule_all(api)
  elif role == 'worker':
    run_task(api)
  else:
    raise ValueError('Unknown role: %s' % role)


def schedule_all(api):
  flutter_path = api.path['start_dir'].join('flutter')
  with api.step.nest('checkout flutter/flutter'):
    api.repo_util.checkout(
        'flutter',
        flutter_path,
        api.properties.get('git_url'),
        api.properties.get('git_ref'),
    )

  env, env_prefixes = api.repo_util.flutter_environment(flutter_path)
  devicelab_path = flutter_path.join('dev', 'devicelab')

  sub_jobs = []
  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    # Reads the manifest.
    result = api.yaml.read(
        'read manifest', devicelab_path.join('manifest.yaml'), api.json.output()
    )
    manifest = result.json.output
    for task_name, task_body in manifest['tasks'].iteritems():
      # Example first capability values: linux/android, mac/ios.
      first_capability = task_body['required_agent_capabilities'][0]
      if task_body.get('on_luci'):
        sub_job = api.job.new(task_name)
        sub_job.properties.update({
            "recipe": api.job.current_recipe(),
            "role": "worker",
            "first_capability": first_capability,
            "git_url": api.properties.get('git_url'),
            "git_ref": api.properties.get('git_ref'),
        })
        # TODO(wutong): add a devicelab dedicated builder that would save us
        # from removing extra dimensions like "cores", "os" etc.
        sub_job.dimensions.update({
            "id": select_bot(first_capability),
            "cores": "",
            "os": "",
            "cpu": "",
            "caches": "",
        })
        sub_jobs.append(sub_job)

  with api.step.nest("launch jobs") as presentation:
    for sub_job in sub_jobs:
      api.job.launch(sub_job, presentation)

  with api.step.nest("collect jobs") as presentation:
    api.job.collect(sub_jobs, presentation)


def select_bot(first_capability):
  # TODO(wutong): apply bot selection by dimensions instead of hard-coded ids.
  mapping = {
      "linux/android": "flutter-devicelab-linux-8",
      "mac/android": "flutter-devicelab-mac-22",
      "mac/ios": "flutter-devicelab-mac-9",
  }
  return mapping.get(first_capability)


def run_task(api):
  task_name = api.properties["name"]
  first_capability = api.properties["first_capability"]

  flutter_path = api.path['start_dir'].join('flutter')
  with api.step.nest('checkout flutter/flutter'):
    api.repo_util.checkout(
        'flutter',
        flutter_path,
        api.properties.get('git_url'),
        api.properties.get('git_ref'),
    )

  env, env_prefixes = api.repo_util.flutter_environment(flutter_path)
  devicelab_path = flutter_path.join('dev', 'devicelab')
  with api.context(env=env, env_prefixes=env_prefixes, cwd=devicelab_path):
    api.step('flutter doctor', ['flutter', 'doctor'])
    api.step('pub get', ['pub', 'get'])

    # Runs a task.
    sdk = first_capability.split('/')[1]
    if sdk == 'android':
      api.flutter_deps.android_sdk(env, env_prefixes, '')
      with api.context(env=env, env_prefixes=env_prefixes):
        api.step(
            'run %s' % task_name, ['dart', 'bin/run.dart', '-t', task_name]
        )
    elif sdk == 'ios':
      run_ios_task(api, task_name)


def run_ios_task(api, task_name):
  api.step('unlock login keychain', ['unlock_login_keychain.sh'])
  # See go/googler-flutter-signing about how to renew the Apple development
  # certificate and provisioning profile.
  code_signing_env = {
      'FLUTTER_XCODE_CODE_SIGN_STYLE': 'Manual',
      'FLUTTER_XCODE_DEVELOPMENT_TEAM': 'S8QB4VV633',
      'FLUTTER_XCODE_PROVISIONING_PROFILE_SPECIFIER': 'match Development *',
  }
  with api.context(env=code_signing_env):
    api.step('run %s' % task_name, ['dart', 'bin/run.dart', '-t', task_name])


def GenTests(api):
  for t in gen_scheduler_tests(api):
    yield t
  for t in gen_worker_tests(api):
    yield t


def gen_scheduler_tests(api):
  yield api.test(
      "unknown_role",
      api.properties(role="unknown"),
      api.expect_exception('ValueError'),
  )

  sample_manifest = {
      "tasks": {
          "android_defines_test": {
              "description": "Builds an APK with a --dart-define ...",
              "stage": "devicelab",
              "required_agent_capabilities": ["linux/android"],
              "on_luci": True,
          },
      },
  }
  yield api.test(
      "schedule", api.properties(role="scheduler"),
      api.repo_util.flutter_environment_data(),
      api.step_data('read manifest.parse', api.json.output(sample_manifest)),
      api.job.mock_collect(["fake-task-id"], "collect jobs")
  )


def gen_worker_tests(api):
  sample_manifest = {
      "tasks": {
          "android_defines_test": {
              "description": "Builds an APK with a --dart-define ...",
              "stage": "devicelab",
              "required_agent_capabilities": ["linux/android"],
              "on_luci": True,
          },
          "flavors_test": {
              "description": "Checks that flavored builds work on Android.",
              "stage": "devicelab",
              "required_agent_capabilities": ["mac/android"],
              "on_luci": True,
          },
          "flutter_gallery_ios__compile": {
              "description": "Collects various performance metrics of ...",
              "stage": "devicelab_ios",
              "required_agent_capabilities": ["mac/ios"],
              "on_luci": True,
          },
      },
  }
  for task_name in sample_manifest["tasks"].keys():
    yield api.test(
        task_name,
        api.properties(
            role="worker",
            name=task_name,
            first_capability=(
                sample_manifest["tasks"][task_name]
                ["required_agent_capabilities"][0]
            ),
            android_sdk_license='android_sdk_hash',
            android_sdk_preview_license='android_sdk_preview_hash',
        ),
        api.repo_util.flutter_environment_data(),
    )
