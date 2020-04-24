#!/usr/bin/env python
# Copyright 2013 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Runs a command with PYTHONPATH set up for the Chromium build setup.

This is helpful for running scripts locally on a development machine.

Try `scripts/tools/runit.py python`
or  (in scripts/slave): `../tools/runit.py runtest.py --help`
"""

import optparse
import os
import subprocess
import sys

# Directory where this script (runit.py) lives (i.e. scripts/tools)
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

# Import 'common.env' from 'scripts' directory to load our Infra PYTHONPATH
sys.path.insert(0, os.path.dirname(SCRIPT_DIR))
import common.env

USAGE = '%s [options] <command to run>' % os.path.basename(sys.argv[0])


def main():
  option_parser = optparse.OptionParser(usage=USAGE)
  option_parser.add_option('-s', '--show-path', action='store_true',
                           help='display new PYTHONPATH before running command')
  option_parser.add_option('--with-third-party-lib', action='store_true',
                           help='use third_party library in the build path.')
  option_parser.disable_interspersed_args()
  options, args = option_parser.parse_args()
  if not args:
    option_parser.error('Must provide a command to run.')

  if args[0] == 'python':
    # If the first argument is 'python' and --with-third-party-lib is not set,
    # it is natural for us to think the user want to use vpython.
    if not options.with_third_party_lib:
      args[0] = 'vpython.bat' if sys.platform == 'win32' else 'vpython'
    else:
      # if --with-third-party is given,
      # replace it with the system executable.
      args[0] = sys.executable

  with common.env.GetInfraPythonPath(
      with_third_party=options.with_third_party_lib).Enter():
    if options.show_path:
      print 'Set PYTHONPATH: %s' % os.environ['PYTHONPATH']
    # Use subprocess instead of execv because otherwise windows destroys
    # quoting.
    return subprocess.call(args)


if __name__ == '__main__':
  sys.exit(main())
