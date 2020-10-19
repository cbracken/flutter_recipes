# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager, nested
from recipe_engine import recipe_api


class FlutterXcodeApi(recipe_api.RecipeApi):

  def __init__(self, sdk_properties, *args, **kwargs):
    super(FlutterXcodeApi, self).__init__(*args, **kwargs)
    self._sdk_properties = sdk_properties.copy()

  @contextmanager
  def __call__(self, kind):
    """Sets up the XCode SDK environment with additional iOS dependencies.

    It is a no-op on non-mac platforms. This method invokes $depot_tools/osx_sdk
    with the given kind, then installs additional iOS dependencies specified in
    $flutter/flutter_osx_sdk.

    Args:
      kind ('mac'|'ios'): The kind to pass to $depot_tools/osx_sdk.
    """
    if self.m.platform.is_mac:
      with self.m.osx_sdk(kind), self._additional_deps():
        yield
    else:
      yield

  @contextmanager
  def _additional_deps(self):
    """Installs additional dependencis specified in $flutter/flutter_osx_sdk."""
    deps = self._sdk_properties
    if not deps:
      yield
      return
    with nested(*map(self._handleDependency, deps.items())):
      yield

  def _handleDependency(self, dependency):
    """Parses an entry in $flutter/flutter_osx_sdk."""
    (name, version) = dependency
    name_lowered = name.lower()
    if name_lowered == 'iphoneos_sdk' or name_lowered == 'iphonesimulator_sdk':
      return self._additional_ios_sdk(name_lowered, version)
    elif name_lowered == 'ld':
      return self._install_ld(version)

  def _ensure_package(self, package_name, version, version_tag_prefix='version:'):
    """Ensures an iOS dependency CIPD package by name and version."""
    base_path = self.m.path['cache'].join(
      'xcode_deps', package_name, version,
    )
    ensureFile = self.m.cipd.EnsureFile()
    ensureFile.add_package(
      'flutter_internal/mac/xcode_deps/%s' % package_name,
      '%s%s' % (version_tag_prefix, version),
    )
    self.m.cipd.ensure(base_path, ensureFile)
    return base_path

  @contextmanager
  def _install_ld(self, version):
    """Setup the ld64 binary to use.

    Typically used in conjuction with additional ios sdks to workaround TAPI
    issues.

    Args:
      version(string): the version number of the ld64 binary to retrieve.
      e.g., 609.
    """
    package_path = self._ensure_package('ld', version)
    ld_temp_dir = self.m.path.mkdtemp()
    bin_dir = ld_temp_dir.join('bin')

    with self.m.step.nest('set up ld64: %s' % version):
      # Copies the bin folder that contains the ld binary.
      self.m.file.copytree('copying ld', package_path.join('bin'), bin_dir)
      # Symlinks the ../lib folder from xcode because
      # ld's LC_RPATH is set to @executable_path/../lib/
      lib_path = self.m.path['cache'].join(
        'osx_sdk', 'XCode.app', 'Contents', 'Developer', 'Toolchains',
        'XcodeDefault.xctoolchain', 'usr', 'lib'
      )
      # No cleanup needed: everything happens in a temp directory.
      self.m.file.symlink('symlinking libs', lib_path, ld_temp_dir.join('lib'))
    with self.m.context(env_prefixes={'PATH':[bin_dir]}):
      yield

  @contextmanager
  def _additional_ios_sdk(self, package_name, version):
    """Installs an additional iPhoneOS/iPhoneSimulator SDK.

    Typically this is only needed for older Xcode to be able to use newer iPhone
    SDKs, not the other way around.

    Args:
      package_name(string): Can be either iphoneos_sdk or iphonesimulator_sdk.
      version(string): the version number of the sdk to retrieve. e.g., 14.0.
    """
    kind = 'iPhoneOS' if package_name == 'iphoneos_sdk' else 'iPhoneSimulator'
    base_path = self.m.path['cache'].join(
      'xcode_deps', package_name, version,
    )
    symlink_filename = '%s%s.sdk' % (kind, version)

    try:
      with self.m.step.nest('set up %s' % symlink_filename):
        ensureFile = self.m.cipd.EnsureFile()
        # TODO(LongCatIsLooong): relocate these CIPD packages to reuse
        # self._ensure_package.
        ensureFile.add_package(
          'flutter_internal/mac/%s' % package_name,
          'sdk_version:%s' % version,
        )
        self.m.cipd.ensure(base_path, ensureFile)

        # Symlink the sdk folder to the right location in Xcode.
        src = base_path.join('%s.sdk' % (kind.lower()))
        dst = self.m.path['cache'].join(
            'osx_sdk', 'XCode.app', 'Contents', 'Developer', 'Platforms',
            '%s.platform' % (kind), 'Developer', 'SDKs', symlink_filename
        )
        # Fails if this is a directory. This makes sure that we don't touch
        # the stock SDK.
        self.m.file.remove('removing existing symlink', dst)
        self.m.file.symlink('symlinking %s' % (symlink_filename), src, dst)
      yield
    finally:
      self.m.file.remove('removing %s' % (symlink_filename), dst)
