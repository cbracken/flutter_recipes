# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contextlib import contextmanager
from recipe_engine import recipe_api

class AndroidSdkApi(recipe_api.RecipeApi):
  """Provides Android SDK environment.

  Expects the android29 cache to be mounted on the swarming bot.
  """

  def install(self):
    """Installs Android SDK in cache."""
    with self.m.step.nest('download Android SDK components'):
      self.m.cipd.ensure(
          self._root().join('platform-tools'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/platform-tools/${platform}',
              'version:29.0.2',
          ),
      )
      self.m.cipd.ensure(
          self._root().join('platforms'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/platforms',
              'version:29r1',
          ),
      )
      self.m.cipd.ensure(
          self._root().join('build-tools'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/build-tools/${platform}',
              'version:29.0.1',
          ),
      )

    with self.m.step.nest('add Android SDK licenses'):
      self.m.file.ensure_directory('mkdir licenses',
                                   self._root().join('licenses'))
      self.m.file.write_text(
          'android sdk license',
          self._root().join('licenses', 'android-sdk-license'),
          str(self.m.properties['android_sdk_license']),
      )
      self.m.file.write_text(
          'android sdk preview license',
          self._root().join('licenses', 'android-sdk-preview-license'),
          str(self.m.properties['android_sdk_preview_license']),
      )

  @contextmanager
  def context(self):
    """Yields a context that contains Android SDK environment.

    Must call api.android_sdk.install() first.
    """
    with self.m.context(
        env={'ANDROID_SDK_ROOT': self._root()},
        env_prefixes={'PATH': [self._root().join('platform-tools')]}):
      yield

  def _root(self):
    return self.m.path['cache'].join('android29')
