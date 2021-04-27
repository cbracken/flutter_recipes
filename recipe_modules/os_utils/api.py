# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
from recipe_engine import recipe_api

from PB.go.chromium.org.luci.buildbucket.proto import common as common_pb2


class FlutterDepsApi(recipe_api.RecipeApi):
  """Operating system utilities."""

  def _kill_win(self, name, exe_name):
    """Kills all the windows processes with a given name.

    Args:
      name(str): The name of the step.
      exe_name(str): The name of the windows executable.
    """
    self.m.step(
        name,
        ['taskkill', '/f', '/im', exe_name, '/t'],
        ok_ret='any',
    )

  def clean_derived_data(self):
    """Cleans the derived data folder in mac builders.

    Derived data caches fail very frequently when different version of mac/ios
    sdks are used in the same bot. To prevent those failures we will start
    deleting the folder before every task.
    """
    derived_data_path = self.m.path['home'].join(
        'Library', 'Developer', 'Xcode', 'DerivedData'
    )
    if self.m.platform.is_mac:
      self.m.step(
          'Delete mac deriveddata',
          ['rm', '-rf', derived_data_path],
          infra_step=True,
      )

  def collect_os_info(self):
    """Collects meminfo, cpu, processes for mac"""
    if self.m.platform.is_mac:
      self.m.step(
          'OS info',
          cmd=['top', '-l', '3', '-o', 'mem'],
          infra_step=True,
      )
      # These are temporary steps to collect xattr info for triage purpose.
      # See issue: https://github.com/flutter/flutter/issues/68322#issuecomment-740264251
      self.m.step(
          'python xattr info',
          cmd=['xattr', '/opt/s/w/ir/cipd_bin_packages/python'],
          ok_ret='any',
          infra_step=True,
      )
      self.m.step(
          'git xattr info',
          cmd=['xattr', '/opt/s/w/ir/cipd_bin_packages/git'],
          ok_ret='any',
          infra_step=True,
      )
    elif self.m.platform.is_linux:
      self.m.step(
          'OS info',
          cmd=['top', '-b', '-n', '3', '-o', '%MEM'],
          infra_step=True,
      )

  def kill_processes(self):
    """Kills processes.

    Windows uses exclusive file locking.  On LUCI, if these processes remain
    they will cause the build to fail because the builder won't be able to
    clean up.

    Linux and Mac have leaking processes after task executions, potentially
    causing the build to fail if without clean up.

    This might fail if there's not actually a process running, which is
    fine.

    If it actually fails to kill the task, the job will just fail anyway.
    """
    with self.m.step.nest('Killing Processes') as presentation:
      if self.m.platform.is_win:
        self._kill_win('stop gradle daemon', 'java.exe')
        self._kill_win('stop dart', 'dart.exe')
        self._kill_win('stop adb', 'adb.exe')
        self._kill_win('stop flutter_tester', 'flutter_tester.exe')
      elif self.m.platform.is_mac:
        self.m.step(
            'kill dart', ['killall', '-9', 'dart'],
            ok_ret='any',
            infra_step=True
        )
        self.m.step(
            'kill flutter', ['killall', '-9', 'flutter'],
            ok_ret='any',
            infra_step=True
        )
        self.m.step(
            'kill Chrome', ['killall', '-9', 'Chrome'],
            ok_ret='any',
            infra_step=True
        )
        self.m.step(
            'kill Safari', ['killall', '-9', 'Safari'],
            ok_ret='any',
            infra_step=True
        )
        self.m.step(
            'kill Safari', ['killall', '-9', 'java'],
            ok_ret='any',
            infra_step=True
        )
        self.m.step(
            'kill Safari', ['killall', '-9', 'adb'],
            ok_ret='any',
            infra_step=True
        )
      else:
        self.m.step(
            'kill chrome', ['pkill', 'chrome'], ok_ret='any', infra_step=True
        )
        self.m.step(
            'kill dart', ['pkill', 'dart'], ok_ret='any', infra_step=True
        )
        self.m.step(
            'kill flutter', ['pkill', 'flutter'], ok_ret='any', infra_step=True
        )
        self.m.step(
            'kill java', ['pkill', 'java'], ok_ret='any', infra_step=True
        )
        self.m.step('kill adb', ['pkill', 'adb'], ok_ret='any', infra_step=True)
      # Ensure we always pass this step as killing non existing processes
      # may create errors.
      presentation.status = 'SUCCESS'

  @contextmanager
  def make_temp_directory(self, label):
    """Makes a temporary directory that is automatically deleted.

    Args:
      label:
        (str) Part of the step name that removes the directory after is used.
    """
    temp_dir = self.m.path.mkdtemp('tmp')
    try:
      yield temp_dir
    finally:
      self.m.file.rmtree('temp dir for %s' % label, temp_dir)

  def shutdown_simulators(self):
    """It stops simulators if task is running on a devicelab bot."""
    if str(self.m.swarming.bot_id
          ).startswith('flutter-devicelab') and self.m.platform.is_mac:
      with self.m.step.nest('Shutdown simulators'):
        self.m.step(
            'Shutdown simulators',
            ['sudo', 'xcrun', 'simctl', 'shutdown', 'all']
        )
        self.m.step(
            'Erase simulators', ['sudo', 'xcrun', 'simctl', 'erase', 'all']
        )

  def dismiss_dialogs(self):
    """Dismisses iOS dialogs to avoid problems.

    Args:
      flutter_path(Path): A path to the checkout of the flutter sdk repository.
    """
    if str(self.m.swarming.bot_id
          ).startswith('flutter-devicelab') and self.m.platform.is_mac:
      with self.m.step.nest('Dismiss dialogs'):
        cocoon_path = self.m.path['cache'].join('cocoon')
        self.m.repo_util.checkout(
            'cocoon', cocoon_path, ref='refs/heads/master'
        )
        resource_name = self.resource('dismiss_dialogs.sh')
        self.m.step(
            'Set execute permission',
            ['chmod', '755', resource_name],
            infra_step=True,
        )
        with self.m.context(
            cwd=cocoon_path.join('device_doctor', 'tool', 'infra-dialog'),
            infra_steps=True,
        ):
          device_id = self.m.step(
              'Find device id', ['idevice_id', '-l'],
              stdout=self.m.raw_io.output()
          ).stdout.rstrip()
          cmd = [resource_name, device_id]
          self.m.step('Run app to dismiss dialogs', cmd)
