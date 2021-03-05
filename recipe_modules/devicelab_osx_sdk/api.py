# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Functions to use fixed xcode installations.

The cost of installing xcode from cold caches is prohibitely high for the
Flutter Devicelab tasks. This module provide functions to use semi-hermetic
Xcode installations pre-installed on Devicelab bots.

XCode build version number. Internally maps to an XCode build id like '9c40b'.
See:
https://chrome-infra-packages.appspot.com/p/flutter_internal/ios/xcode/mac/+/
for an up to date list of the latest SDK builds.
"""

from contextlib import contextmanager

from recipe_engine import recipe_api


class DevicelabOSXSDKApi(recipe_api.RecipeApi):
  """API for using OS X SDK distributed via CIPD."""

  def __init__(self, sdk_properties, *args, **kwargs):
    super(DevicelabOSXSDKApi, self).__init__(*args, **kwargs)
    self._sdk_properties = sdk_properties
    self._sdk_version = None
    self._tool_pkg = 'infra/tools/mac_toolchain/${platform}'
    self._tool_ver = 'latest'

  def initialize(self):
    """Initializes xcode, and ios versions.

    Versions are passed as recipe properties.
    """
    if not self.m.platform.is_mac:
      return

    if 'sdk_version' in self._sdk_properties:
      self._sdk_version = self._sdk_properties['sdk_version'].lower()

  @contextmanager
  def __call__(self, kind):
    """Sets up the XCode SDK environment.

    Is a no-op on non-mac platforms.

    This will deploy the helper tool and the XCode.app bundle at
    `/opt/flutter/xcode/<version>`.

    Usage:
      with api.devicelab_osx_sdk('mac'):
        # sdk with mac build bits

      with api.devicelab_osx_sdk('ios'):
        # sdk with mac+iOS build bits

    Args:
      kind ('mac'|'ios'): How the SDK should be configured. iOS includes the
        base XCode distribution, as well as the iOS simulators (which can be
        quite large).

    Raises:
        StepFailure or InfraFailure.
    """
    assert kind in ('mac', 'ios'), 'Invalid kind %r' % (kind,)
    if not self.m.platform.is_mac:
      yield
      return

    try:
      with self.m.context(infra_steps=True):
        app = '/opt/flutter/xcode/%s/XCode.app' % self._sdk_version
        self._ensure_sdk(kind, app)
        self.m.step('select XCode', ['sudo', 'xcode-select', '--switch', app])
      yield
    finally:
      with self.m.context(infra_steps=True):
        self.m.step('reset XCode', ['sudo', 'xcode-select', '--reset'])

  def _ensure_sdk(self, kind, app):
    """Ensures the mac_toolchain tool and OS X SDK packages are installed."""
    tool_dir = self.m.path.mkdtemp().join('osx_sdk')
    ef = self.m.cipd.EnsureFile()
    ef.add_package(self._tool_pkg, self._tool_ver)
    self.m.cipd.ensure(tool_dir, ef)
    self.m.step(
        'install xcode', [
            tool_dir.join('mac_toolchain'),
            'install',
            '-kind',
            kind,
            '-xcode-version',
            self._sdk_version,
            '-output-dir',
            app,
            '-cipd-package-prefix',
            'flutter_internal/ios/xcode',
        ]
    )
