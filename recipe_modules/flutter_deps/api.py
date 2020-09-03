# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class FlutterDepsApi(recipe_api.RecipeApi):
  """Utilities to install flutter build/test dependencies at runtime."""

  def required_deps(self, env, env_prefixes, deps):
    """Install all the required dependencies for a given builder.

    Args:
      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
      deps(list(dict)): A list of dictionaries with dependencies as
        {'dependency': 'android_sdk', version: ''} where an empty version
        means the default.
    """
    available_deps = {
        'open_jdk': self.open_jdk, 'goldctl': self.goldctl,
        'chrome_and_driver': self.chrome_and_driver, 'go_sdk': self.go_sdk,
        'dashing': self.dashing, 'vpython': self.vpython
    }
    for dep in deps:
      dep_funct = available_deps.get(dep.get('dependency'))
      if not dep_funct:
        raise ValueError('Dependency %s not available.' % dep)
      dep_funct(env, env_prefixes, dep.get('version'))

  def open_jdk(self, env, env_prefixes, version):
    """Downloads OpenJdk CIPD package and updates environment variables.

    Args:
      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
      version(str): The OpenJdk version to install.
    """
    version = version or 'version:1.8.0u202-b08'
    with self.m.step.nest('OpenJDK dependency'):
      java_cache_dir = self.m.path['cache'].join('java')
      self.m.cipd.ensure(
          java_cache_dir,
          self.m.cipd.EnsureFile().add_package(
              'flutter_internal/java/openjdk/${platform}', version
          )
      )
      env['JAVA_HOME'] = java_cache_dir
      path = env_prefixes.get('PATH', [])
      path.append(java_cache_dir.join('bin'))
      env_prefixes['PATH'] = path

  def goldctl(self, env, env_prefixes, version):
    """Downloads goldctl from CIPD and updates the environment variables.

    Args:
      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
      version(str): The goldctl version to install.
    """
    version = version or 'git_revision:b57f561ad4ad624bd399b8b7b500aa1955276d41'
    with self.m.step.nest('Download goldctl'):
      goldctl_cache_dir = self.m.path['cache'].join('gold')
      self.m.cipd.ensure(
          goldctl_cache_dir,
          self.m.cipd.EnsureFile().add_package(
              'skia/tools/goldctl/${platform}', version
          )
      )
      env['GOLDCTL'] = goldctl_cache_dir.join('goldctl')

    if self.m.properties.get('git_ref') and self.m.properties.get('gold_tryjob'
                                                                 ) == True:
      env['GOLD_TRYJOB'] = self.m.properties.get('git_ref')

  def chrome_and_driver(self, env, env_prefixes, version):
    """Downloads chrome from CIPD and updates the environment variables.

    Args:
      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
      version(str): The OpenJdk version to install.
    """
    version = version or 'latest'
    with self.m.step.nest('Chrome and driver dependency'):
      env['CHROME_NO_SANDBOX'] = 'true'
      chrome_path = self.m.path['cache'].join('chrome', 'chrome')
      pkgs = self.m.cipd.EnsureFile()
      pkgs.add_package('flutter_internal/browsers/chrome/${platform}', version)
      self.m.cipd.ensure(chrome_path, pkgs)
      chrome_driver_path = self.m.path['cache'].join('chrome', 'drivers')
      pkgdriver = self.m.cipd.EnsureFile()
      pkgdriver.add_package(
          'flutter_internal/browser-drivers/chrome/${platform}', version
      )
      self.m.cipd.ensure(chrome_driver_path, pkgdriver)
      paths = env_prefixes.get('PATH', [])
      paths.append(chrome_path)
      paths.append(chrome_driver_path)
      env_prefixes['PATH'] = paths
      binary_name = 'chrome.exe' if self.m.platform.is_win else 'chrome'
      env['CHROME_EXECUTABLE'] = chrome_path.join(binary_name)

  def go_sdk(self, env, env_prefixes, version):
    """Installs go sdk."""
    version = version or 'version:1.12.5'
    go_path = self.m.path['cache'].join('go')
    go = self.m.cipd.EnsureFile()
    go.add_package('infra/go/${platform}', version)
    self.m.cipd.ensure(go_path, go)
    paths = env_prefixes.get('PATH', [])
    paths.append(go_path.join('bin'))
    # Setup GOPATH and add to the env.
    bin_path = self.m.path['cleanup'].join('go_path')
    self.m.file.ensure_directory('Ensure go path', bin_path)
    env['GOPATH'] = bin_path
    paths.append(bin_path)
    env_prefixes['PATH'] = paths

  def dashing(self, env, env_prefixes, version):
    """Installs dashing."""
    version = version or 'git_revision:ed8da90e524f59c69781c8af65638f108d0bbba6'
    self.go_sdk(env, env_prefixes, 'latest')
    with self.m.context(env=env, env_prefixes=env_prefixes):
      self.m.step(
          'Install dashing',
          ['go', 'get', '-u', 'github.com/technosophos/dashing']
      )

  def vpython(self, env, env_prefixes, version):
    """Installs vpython."""
    version = version or 'latest'
    vpython_path = self.m.path['cache'].join('vpython')
    vpython = self.m.cipd.EnsureFile()
    vpython.add_package('infra/tools/luci/vpython/${platform}', version)
    self.m.cipd.ensure(vpython_path, vpython)
    paths = env_prefixes.get('PATH', [])
    paths.append(vpython_path)
    env_prefixes['PATH'] = paths
