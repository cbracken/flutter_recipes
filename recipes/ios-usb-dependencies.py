# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager

DEPS = [
    'build/build',
    'build/zip',
    'depot_tools/git',
    'depot_tools/gsutil',
    'depot_tools/depot_tools',
    'depot_tools/osx_sdk',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/step',
    'recipe_engine/url',
]

BUCKET_NAME = 'flutter_infra'
HOMEBREW_FLUTTER_PREFIX = ['flutter', 'homebrew-flutter']
MIRROR_URL_PREFIX = 'https://flutter-mirrors.googlesource.com'

INSTALL_PKGS = {
    'ideviceinstaller-flutter': {
      'install_flags': ['--HEAD'],
      'deliverables': [
        'bin/ideviceinstaller',
        'COPYING',
        ],
      },
    'libplist-flutter': {
      'install_flags': ['--HEAD'],
      'deliverables': [
        'lib/libplist.3.dylib',
        'COPYING',
        ],
      },
    'usbmuxd-flutter': {
      'install_flags': ['--HEAD'],
      'deliverables': [
        'lib/libusbmuxd.4.dylib',
        'bin/iproxy',
        'COPYING',
        ],
      },
    'openssl-flutter': {
      'install_flags': ['--HEAD'],
      'deliverables': [
        'lib/libssl.1.0.0.dylib',
        'lib/libcrypto.1.0.0.dylib',
        'LICENSE',
        ],
      },
    'libimobiledevice-flutter': {
      'install_flags': ['--HEAD'],
      'deliverables': [
        'COPYING',
        'COPYING.LESSER',
        'libtasn1-LICENSE',
        'libtasn1-AUTHORS',
        'bin/idevice_id',
        'bin/ideviceinfo',
        'bin/idevicename',
        'bin/idevicescreenshot',
        'bin/idevicesyslog',
        'lib/libimobiledevice.6.dylib',
        ],
      },
    'ios-deploy-flutter': {
      'install_flags': ['--HEAD'],
      'deliverables': [
        'bin/ios-deploy',
        'LICENSE',
        'LICENSE2',
        ],
      },
 }

def InstallHomebrew(api, homebrew_dir):
  homebrew_tar = api.path['start_dir'].join('homebrew.tar.gz')
  api.file.ensure_directory('mkdir homebrew', homebrew_dir)
  api.step('get homebrew', [
    'curl',
    '-L',
    'https://github.com/Homebrew/brew/tarball/master',
    '-o',
    homebrew_tar])
  api.step('open tarball', [
    'tar',
    'zxf',
    homebrew_tar,
    '--strip',
    '1',
    '-C',
    homebrew_dir])

def GetBrewBin(api):
  return api.path['start_dir'].join('homebrew', 'bin', 'brew')

def TapCustomBrews(api):
  api.step('tap custom formulae', [
    str(GetBrewBin(api)),
    'tap',
    '/'.join(HOMEBREW_FLUTTER_PREFIX),
    '%s/homebrew-flutter' % MIRROR_URL_PREFIX])

def GetLocalPath(api, package_name):
  return api.path['start_dir'].join('homebrew', 'opt', package_name)

def GetCloudPath(api, package_name):
  '''Location of cloud bucket for unsigned binaries'''
  commit_hash = GetCommitHash(api)
  short_name = package_name.replace('-flutter', '')
  return 'ios-usb-dependencies/unsigned/%s/%s/%s.zip' % (
      short_name,
      commit_hash,
      short_name)

def GetCommitHash(api):
  return api.buildbucket.gitiles_commit.id

def InstallPackage(api, package, name):
  install_flags = package.get('install_flags', [])
  prefix = '/'.join(HOMEBREW_FLUTTER_PREFIX)
  api.step('installing %s' % name, [
    str(GetBrewBin(api)),
    'install',
    '/'.join([prefix, name]),
    ] + install_flags)

def CopyDeliverable(api, deliverable, name, output_path):
  deliverable_path = GetLocalPath(api, name).join(deliverable)
  api.file.copy('copying %s from package %s' % (deliverable, name),
      deliverable_path,
      output_path,
      )

def ZipAndUploadDeliverables(api, package_name, input_path, zip_out_dir):
  file_name = '%s.zip' % package_name
  output_path = zip_out_dir.join(file_name)
  api.zip.directory('zipping %s' % file_name, input_path, output_path)
  cloud_path = GetCloudPath(api, package_name)
  api.step('cloud path', ['echo', cloud_path])
  api.gsutil.upload(
      output_path,
      BUCKET_NAME,
      cloud_path,
      link_name=file_name,
      name='upload of %s' % file_name,
      )

def RunSteps(api):
  work_dir = api.path['start_dir']
  homebrew_dir = work_dir.join('homebrew')
  InstallHomebrew(api, homebrew_dir)

  output_dir = work_dir.join('output')
  api.file.ensure_directory('mkdir output', output_dir)

  zip_out_dir = work_dir.join('zips')
  api.file.ensure_directory('mkdir zips', zip_out_dir)

  TapCustomBrews(api)

  package_name = api.properties['package_name']
  package = INSTALL_PKGS[package_name]

  with api.osx_sdk('mac'):
    InstallPackage(api, package, package_name)

  package_out_dir = output_dir.join(package_name)
  api.file.ensure_directory(
      'mkdir package %s' % package_out_dir,
      package_out_dir)

  if len(package['deliverables']) > 0:
    for deliverable in package['deliverables']:
      CopyDeliverable(api, deliverable, package_name, package_out_dir)

    ZipAndUploadDeliverables(api, package_name, package_out_dir, zip_out_dir)

def GenTests(api):
  for package_name in INSTALL_PKGS:
    yield api.test(
        package_name,
        api.properties(package_name=package_name),
        api.buildbucket.ci_build(git_ref='refs/heads/master'),
    )

# vim: ts=2 sw=2
