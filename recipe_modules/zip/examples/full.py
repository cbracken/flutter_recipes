# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'recipe_engine/context',
  'recipe_engine/file',
  'recipe_engine/path',
  'recipe_engine/platform',
  'recipe_engine/step',
  'zip',
]

def RunSteps(api):
  # Prepare files.
  temp = api.path.mkdtemp('zip-example')
  api.step('touch a', ['touch', temp.join('a')])
  api.step('touch b', ['touch', temp.join('b')])
  api.file.ensure_directory('mkdirs', temp.join('sub', 'dir'))
  api.step('touch c', ['touch', temp.join('sub', 'dir', 'c')])

  # Build zip using 'zip.directory'.
  api.zip.directory('zipping', temp, temp.join('output.zip'))

  # Build a zip using ZipPackage api.
  package = api.zip.make_package(temp, temp.join('more.zip'))
  package.add_file(package.root.join('a'))
  package.add_file(package.root.join('b'))
  package.add_directory(package.root.join('sub'))
  package.zip('zipping more')

  # Coverage for 'output' property.
  api.step('report', ['echo', package.output])

  # Unzip the package.
  api.zip.unzip('unzipping', temp.join('output.zip'), temp.join('output'),
                quiet=True)
  # List unzipped content.
  with api.context(cwd=temp.join('output')):
    api.step('listing', ['find'])
  # Clean up.
  api.file.rmtree('cleanup', temp)


def GenTests(api):
  for platform in ('linux', 'win', 'mac'):
    yield api.test(
        platform,
        api.platform.name(platform),
    )
