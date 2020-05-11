# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Standalone python script to zip a set of files. Intended to be used by 'zip'
recipe module internally. Should not be used elsewhere.
"""

import json
import os
import subprocess
import sys
import zipfile


def zip_with_subprocess(root, output, entries):
  """Zips set of files and directories using 'zip' utility.

  Works only on Linux and Mac, uses system 'zip' program.

  Args:
    root: absolute path to a directory that will become a root of the archive.
    output: absolute path to a destination archive.
    entries: list of dicts, describing what to zip, see zip/api.py.

  Returns:
    Exit code (0 on success).
  """
  # Collect paths relative to |root| of all items we'd like to zip.
  items_to_zip = []
  for entry in entries:
    tp = entry['type']
    path = entry['path']
    if tp == 'file':
      # File must exist and be inside |root|.
      assert os.path.isfile(path), path
      assert path.startswith(root), path
      items_to_zip.append(path[len(root):])
    elif entry['type'] == 'dir':
      # Append trailing '/'.
      path = path.rstrip(os.path.sep) + os.path.sep
      # Directory must exist and be inside |root| or be |root| itself.
      assert os.path.isdir(path), path
      assert path.startswith(root), path
      items_to_zip.append(path[len(root):] or '.')
    else:
      raise AssertionError('Invalid entry type: %s' % (tp,))

  # Invoke 'zip' in |root| directory, passing all relative paths via stdin.
  proc = subprocess.Popen(
      args=['zip', '-1', '--recurse-paths', '--symlinks', '-@', output],
      stdin=subprocess.PIPE,
      cwd=root)
  proc.communicate('\n'.join(items_to_zip))
  return proc.returncode


def zip_with_python(root, output, entries):
  """Zips set of files and directories using 'zipfile' python module.

  Works everywhere where python works (Windows and Posix).

  Args:
    root: absolute path to a directory that will become a root of the archive.
    output: absolute path to a destination archive.
    entries: list of dicts, describing what to zip, see zip/api.py.

  Returns:
    Exit code (0 on success).
  """
  with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED,
                       allowZip64=True) as zip_file:
    def add(path, archive_name):
      assert path.startswith(root), path
      # Do not add itself to archive.
      if path == output:
        return
      if archive_name is None:
        archive_name = path[len(root):]
      print 'Adding %s' % archive_name
      zip_file.write(path, archive_name)

    for entry in entries:
      tp = entry['type']
      path = entry['path']
      if tp == 'file':
        add(path, entry.get('archive_name'))
      elif tp == 'dir':
        for cur, _, files in os.walk(path):
          for name in files:
            add(os.path.join(cur, name), None)
      else:
        raise AssertionError('Invalid entry type: %s' % (tp,))
  return 0


def use_python_zip(entries):
  if sys.platform == 'win32':
    return True
  for entry in entries:
    if entry.get('archive_name') is not None:
      return True
  return False


def main():
  # See zip/api.py, def zip(...) for format of |data|.
  data = json.load(sys.stdin)
  entries = data['entries']
  output = data['output']
  root = data['root'].rstrip(os.path.sep) + os.path.sep

  # Archive root directory should exist and be an absolute path.
  assert os.path.exists(root), root
  assert os.path.isabs(root), root

  # Output zip path should be an absolute path.
  assert os.path.isabs(output), output

  print 'Zipping %s...' % output
  exit_code = -1
  try:
    if use_python_zip(entries):
      # Used on Windows, since there's no builtin 'zip' utility there, and when
      # an explicit archive_name is set, since there's no way to do that with
      # the native zip utility without filesystem shenanigans
      exit_code = zip_with_python(root, output, entries)
    else:
      # On mac and linux 'zip' utility handles symlink and file modes.
      exit_code = zip_with_subprocess(root, output, entries)
  finally:
    # On non-zero exit code or on unexpected exception, clean up.
    if exit_code:
      try:
        os.remove(output)
      except:  # pylint: disable=bare-except
        pass
  if not exit_code:
    print 'Archive size: %.1f KB' % (os.stat(output).st_size / 1024.0,)
  return exit_code


if __name__ == '__main__':
  sys.exit(main())
