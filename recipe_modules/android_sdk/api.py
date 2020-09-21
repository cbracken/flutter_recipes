# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from contextlib import contextmanager
from recipe_engine import recipe_api


class AndroidSdkApi(recipe_api.RecipeApi):
  """Provides Android SDK environment.

  Expects the android29 cache to be mounted on the swarming bot.
  """

  def install(self, sdk_root, env, env_prefixes):
    """Installs Android SDK in cache.

    Args:
      sdk_root(Path): The path to install the different android packages.
      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
    """
    with self.m.step.nest('download Android SDK components'):
      self.m.cipd.ensure(
          sdk_root.join('tools'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/tools/${platform}',
              'version:26.1.1',
          ),
      )
      self.m.cipd.ensure(
          sdk_root.join('platform-tools'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/platform-tools/${platform}',
              'version:29.0.2',
          ),
      )
      self.m.cipd.ensure(
          sdk_root.join('platforms'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/platforms',
              'version:29r1',
          ),
      )
      self.m.cipd.ensure(
          sdk_root.join('build-tools'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/sdk/build-tools/${platform}',
              'version:29.0.1',
          ),
      )
      self.m.cipd.ensure(
          sdk_root.join('ndk-bundle'),
          self.m.cipd.EnsureFile().add_package(
              'flutter/android/ndk/${platform}',
              'version:21.3.6528147',
          ),
      )
      self.m.cipd.ensure(
          sdk_root.join('licenses'),
          self.m.cipd.EnsureFile().add_package(
              'flutter_internal/android/sdk/licenses',
              'latest',
          ),
      )

    # Setup environment variables
    env['ANDROID_SDK_ROOT'] = sdk_root
    env['ANDROID_HOME'] = sdk_root
    paths = env_prefixes.get('PATH', [])
    paths.append(sdk_root.join('platform-tools'))
    paths.append(sdk_root.join('tools'))
    env_prefixes['PATH'] = paths
