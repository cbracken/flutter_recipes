# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager
from recipe_engine import recipe_api


class AndroidSdkApi(recipe_api.RecipeApi):
  """Provides Android SDK environment."""

  def install(self):
    """Installs Android SDK in cache."""
    android_root = self.m.path['cache'].join('android_root')
    with self.m.step.nest('Download Android SDK Components'):
      self.m.cipd.ensure(
          android_root.join('platform-tools'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/platform-tools/${platform}',
              'version:29.0.2',
          ),
      )
      self.m.cipd.ensure(
          android_root.join('platforms'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/platforms/${platform}',
              'version:29r1.experiment2',
          ),
      )
      self.m.cipd.ensure(
          android_root.join('build-tools'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/build-tools/${platform}',
              'version:29.0.1',
          ),
      )

    with self.m.step.nest('Android SDK Licenses'):
      self.m.file.ensure_directory('mkdir licenses',
                                   android_root.join('licenses'))
      self.m.file.write_text(
          'android sdk license',
          android_root.join('licenses', 'android-sdk-license'),
          str(self.m.properties['android_sdk_license']),
      )
      self.m.file.write_text(
          'android sdk preview license',
          android_root.join('licenses', 'android-sdk-preview-license'),
          str(self.m.properties['android_sdk_preview_license']),
      )

  @contextmanager
  def context(self):
    """Yields a context that contains Android SDK environment.

    Must call api.android_sdk.install() first.
    """
    android_root = self.m.path['cache'].join('android_root')
    with self.m.context(
        env={'ANDROID_SDK_ROOT': android_root},
        env_prefixes={'PATH': [android_root.join('platform-tools')]}):
      yield
