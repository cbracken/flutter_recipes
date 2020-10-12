# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
from recipe_engine import recipe_api

from PB.go.chromium.org.luci.buildbucket.proto import common as common_pb2


class FlutterDepsApi(recipe_api.RecipeApi):
  """Operating system utilities."""

  def _kill_all(self, name, exe_name):
    """Kills all the windows processes with a given name.

    Args:
      name(str): The name of the step.
      exe_name(str): The name of the windows executable.
    """
    self.m.step(name, ['taskkill', '/f', '/im', exe_name, '/t'], ok_ret='any')

  def clean_derived_data(self):
    """Cleans the derived data folder in mac builders.

    Derived data caches fail very frequently when different version of mac/ios
    sdks are used in the same bot. To prevent those failures we will start
    deleting the folder before every task.
    """
    if self.m.platform.is_mac:
      self.m.step(
          'Delete mac deriveddata', [
              'rm', '-rf',
              '/Users/chrome-bot/Library/Developer/Xcode/DerivedData/'
          ]
      )

  def collect_os_info(self):
    """Collects meminfo, cpu, processes for mac"""
    if self.m.platform.is_mac:
      self.m.step('OS info', cmd=['top', '-l', '3', '-n30', '-o', 'mem'])

  def kill_win_processes(self):
    """Kills windows processes.

    Windows uses exclusive file locking.  On LUCI, if these processes remain
    they will cause the build to fail because the builder won't be able to
    clean up.

    This might fail if there's not actually a process running, which is
    fine.

    If it actually fails to kill the task, the job will just fail anyway.
    """
    if self.m.platform.is_win:
      with self.m.step.nest('Killing Windows Processes') as presentation:
        self._kill_all('stop gradle daemon', 'java.exe')
        self._kill_all('stop dart', 'dart.exe')
        self._kill_all('stop adb', 'adb.exe')
        self._kill_all('stop flutter_tester', 'flutter_tester.exe')
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
