# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Standalone python script to unzip an archive. Intended to be used by 'zip'
recipe module internally. Should not be used elsewhere.
"""

import json
import os
import shutil
import subprocess
import sys
import zipfile


def unzip_with_subprocess(zip_file, output, quiet):
  """Unzips an archive using 'zip' utility.

  Works only on Linux and Mac, uses system 'zip' program.

  Args:
    zip_file: absolute path to an archive to unzip.
    output: existing directory to unzip to.
    quiet (bool): If True, instruct the subprocess to unzip with
        minimal output.

  Returns:
    Exit code (0 on success).
  """
  args = ['unzip']
  if quiet:
    args += ['-q']
  args += [zip_file]

  return subprocess.call(
      args=args,
      cwd=output)


def unzip_with_python(zip_file, output):
  """Unzips an archive using 'zipfile' python module.

  Works everywhere where python works (Windows and Posix).

  Args:
    zip_file: absolute path to an archive to unzip.
    output: existing directory to unzip to.

  Returns:
    Exit code (0 on success).
  """
  with zipfile.ZipFile(zip_file) as zip_file_obj:
    for name in zip_file_obj.namelist():
      print 'Extracting %s' % name
      zip_file_obj.extract(name, output)
  return 0


def main():
  # See zip/api.py, def unzip(...) for format of |data|.
  data = json.load(sys.stdin)
  output = data['output']
  zip_file = data['zip_file']
  quiet = data['quiet']

  # Archive path should exist and be an absolute path to a file.
  assert os.path.exists(zip_file), zip_file
  assert os.path.isfile(zip_file), zip_file

  # Output path should be an absolute path, and should NOT exist.
  assert os.path.isabs(output), output
  assert not os.path.exists(output), output

  print 'Unzipping %s...' % zip_file
  exit_code = -1
  try:
    os.makedirs(output)
    if sys.platform == 'win32':
      # Used on Windows, since there's no builtin 'unzip' utility there.
      exit_code = unzip_with_python(zip_file, output)
    else:
      # On mac and linux 'unzip' utility handles symlink and file modes.
      exit_code = unzip_with_subprocess(zip_file, output, quiet)
  finally:
    # On non-zero exit code or on unexpected exception, clean up.
    if exit_code:
      shutil.rmtree(output, ignore_errors=True)
  return exit_code


if __name__ == '__main__':
  sys.exit(main())
