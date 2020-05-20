# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
from recipe_engine import recipe_api

BUCKET_NAME = 'flutter_infra'
FUCHSIA_IMAGE_NAME = 'generic-x64.tgz'
FUCHSIA_PACKAGES_ARCHIVE_NAME = 'generic-x64.tar.gz'
FUCHSIA_TEST_SCRIPT_NAME = 'run_fuchsia_tests.sh'

SSH_CONFIG = """
Host *
  CheckHostIP no
  StrictHostKeyChecking no
  ForwardAgent no
  ForwardX11 no
  GSSAPIDelegateCredentials no
  UserKnownHostsFile /dev/null
  User fuchsia
  IdentitiesOnly yes
  IdentityFile $FUCHSIA_PRIVATE_KEY
  ControlPersist yes
  ControlMaster auto
  ControlPath /tmp/fuchsia--%r@%h:%p
  ConnectTimeout 10
  ServerAliveInterval 1
  ServerAliveCountMax 10
  LogLevel ERROR
"""


class FuchsiaUtilsApi(recipe_api.RecipeApi):
  """Provides utilities to execute fuchsia tests."""

  @contextmanager
  def make_temp_dir(self, label):
    temp_dir = self.m.path.mkdtemp('tmp')
    try:
      yield temp_dir
    finally:
      self.m.file.rmtree('temp dir for %s' % label, temp_dir)

  def download_fuchsia_deps(self, fuchsia_dir, destination_path):
    with self.m.step.nest('Download Fuchsia Dependencies'):
      manifest_path = fuchsia_dir.join('meta', 'manifest.json')
      manifest_data = self.m.file.read_json('Read fuchsia manifest',
                                            manifest_path)
      build_id = manifest_data['id']
      bucket_name = 'fuchsia'
      self.m.gsutil.download(
          bucket_name,
          'development/%s/images/%s' % (build_id, FUCHSIA_IMAGE_NAME),
          destination_path,
          name="download fuchsia system image")
      self.m.gsutil.download(
          bucket_name,
          'development/%s/packages/%s' %
          (build_id, FUCHSIA_PACKAGES_ARCHIVE_NAME),
          destination_path,
          name="download fuchsia companion packages")

  def copy_tool_deps(self, checkout_path, destination_path):
    flutter_bin = checkout_path.join('bin')
    fuchsia_dir = flutter_bin.join('cache', 'artifacts', 'fuchsia')
    fuchsia_tools = fuchsia_dir.join('tools')
    self.download_fuchsia_deps(fuchsia_dir, destination_path)
    with self.m.step.nest('Collect tool deps'):
      self.m.file.copy(
          'Copy test script',
          checkout_path.join('dev', 'bots', FUCHSIA_TEST_SCRIPT_NAME),
          destination_path)
      self.m.file.copy('Copy dev_finder', fuchsia_tools.join('dev_finder'),
                       destination_path)
      self.m.file.copy('Copy pm', fuchsia_tools.join('pm'), destination_path)

  def collect_results(self, fuchsia_swarming_metadata, timeout='30m'):
    # Collect the result of the task by metadata.
    fuchsia_output = self.m.path['cleanup'].join('fuchsia_test_output')
    self.m.file.ensure_directory('swarming output', fuchsia_output)
    results = self.m.swarming.collect(
        'collect',
        fuchsia_swarming_metadata,
        output_dir=fuchsia_output,
        timeout=timeout)
    self.m.display_util.display_tasks(
        'Display builds',
        results=results,
        metadata=fuchsia_swarming_metadata,
        raise_on_failure=True)

  def isolate_deps(self, checkout_path):
    with self.m.step.nest('Create Isolate Archive'):
      with self.make_temp_dir('isolate_dir') as isolate_dir:
        self.copy_tool_deps(checkout_path, isolate_dir)
        isolated_flutter = isolate_dir.join('flutter')
        self.m.file.copytree('Copy flutter framework', checkout_path,
                             isolated_flutter)
        isolated = self.m.isolated.isolated(isolate_dir)
        isolated.add_dir(isolate_dir)
        return isolated.archive('Archive Fuchsia Test Isolate')

  def trigger_swarming_task(self, checkout_path):
    isolated_hash = self.isolate_deps(checkout_path)
    fuchsia_ctl_package = self.m.cipd.EnsureFile()
    fuchsia_ctl_package.add_package(
        'flutter/fuchsia_ctl/${platform}',
        self.m.properties.get('fuchsia_ctl_version'))
    request = (
        self.m.swarming.task_request().with_name(
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

    return self.m.swarming.trigger(
        'Trigger Fuchsia Driver Tests', requests=[request])

  def run_test(self, checkout_path):
    with self.m.step.nest('Fuchsia Tests'):
      self.m.step(
          'Precache Flutter Artifacts',
          ['flutter', 'precache', '--fuchsia', '--no-android', '--no-ios'])
      self.m.step('Precache Flutter Runners', [
          'flutter', 'precache', '--flutter_runner', '--no-android', '--no-ios'
      ])
      return self.trigger_swarming_task(checkout_path)

  def device_name(self):
    """Extracts the device name from the bot name.

    This function expects a bot name [host]--[device_name] where host
    is the hostname the bot is running on and [device_name] is the
    fuchsia device name, e.g. fuchsia-tests-lab01-0001--ocean-bats-wick-snub.
    """
    return self.m.swarming.bot_id.split('--')[1]

  def fuchsia_environment(self, checkout_path):
    env, env_paths = self.m.repo_util.flutter_environment(checkout_path)
    private_key_path = '/etc/botanist/keys/id_rsa_infra'
    config_path = self.m.path['cleanup'].join('fuchsia_ssh__config')
    public_key_path = self.m.path['cleanup'].join('fuchsia_key.pub')
    with self.m.step.nest('Prepare Environment'):
      self.m.step(
          'Create public key', ['ssh-keygen', '-y', '-f', private_key_path],
          stdout=self.m.raw_io.output(leak_to=public_key_path))
      self.m.file.write_raw('Create ssh_config', config_path, SSH_CONFIG)
    env['FUCHSIA_SSH_CONFIG'] = config_path
    env['FUCHSIA_PRIVATE_KEY'] = private_key_path
    env['FUCHSIA_PUBLIC_KEY'] = public_key_path
    return env, env_paths
