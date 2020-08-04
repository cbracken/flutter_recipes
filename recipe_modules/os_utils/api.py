# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class FlutterDepsApi(recipe_api.RecipeApi):
  """Operating system utilities."""

  def _kill_all(self, name, exe_name):
    """Kills all the windows processes with a given name.

    Args:
      name(str): The name of the step.
      exe_name(str): The name of the windows executable.
    """
    self.m.step(name, ['taskkill', '/f', '/im', exe_name, '/t'], ok_ret='any')

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
      with self.m.step.nest('Killing Windows Processes'):
        self._kill_all('stop gradle daemon', 'java.exe')
        self._kill_all('stop dart', 'dart.exe')
        self._kill_all('stop adb', 'adb.exe')
