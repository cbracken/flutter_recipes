# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from recipe_engine import recipe_api


class FlutterDepsApi(recipe_api.RecipeApi):
  """Utilities to install flutter build/test dependencies at runtime."""

  def flutter_engine(self, env, env_prefixes):
    """ Sets the local engine related information to environment variables.

    If the drone is started to run the tests with a local engine, it will
    contain an `isolated_hash` property where we can download engine files.

    These files will be located under `host_debug_unopt` folder.
    Args:

      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
    """
    # No-op if `isolate_hash` property is empty.
    if self.m.properties.get('isolated_hash'):
      isolated_hash = self.m.properties.get('isolated_hash')
      checkout_engine = self.m.path['cache'].join('builder', 'src', 'out')
      # Download host_debug_unopt from the isolate.
      self.m.isolated.download(
          'Download for engine', isolated_hash, checkout_engine
      )
      local_engine = checkout_engine.join('host_debug_unopt')
      dart_bin = local_engine.join('dart-sdk', 'bin')
      paths = env_prefixes.get('PATH', [])
      paths.insert(0, dart_bin)
      env_prefixes['PATH'] = paths
      env['LOCAL_ENGINE'] = local_engine

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
        'dashing': self.dashing, 'vpython': self.vpython,
        'android_sdk': self.android_sdk
    }
    for dep in deps:
      if dep.get('dependency') in ['xcode', 'gems']:
        continue
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
      java_home = java_cache_dir
      if self.m.platform.is_mac:
        java_home = java_cache_dir.join('contents', 'Home')

      env['JAVA_HOME'] = java_home
      path = env_prefixes.get('PATH', [])
      path.append(java_home.join('bin'))
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

  def android_sdk(self, env, env_prefixes, version):
    """Installs android sdk."""
    version = version or '29.0.2'
    root_path = self.m.path['cache'].join('android')
    self.m.android_sdk.install(root_path, env, env_prefixes)

  def swift(self):
    """Installs apple swift.

    Xcode cipd packages do not include swift which is required for some sdk tests.
    """
    swift_path = self.m.path['cleanup'].join('swift')
    swift = self.m.cipd.EnsureFile()
    swift.add_package('flutter_internal/mac/swift/${platform}', 'latest')
    dst = self.m.path['cache'].join(
        'osx_sdk', 'XCode.app', 'Contents', 'Developer', 'Toolchains',
        'XcodeDefault.xctoolchain', 'usr', 'lib'
    )
    with self.m.step.nest('Swift deps'):
      self.m.cipd.ensure(swift_path, swift)
      if self.m.path.exists(dst.join('swift')):
        self.m.file.rmtree('Delete swift', dst.join('swift'))
      self.m.file.copytree(
          'Copy swift', swift_path.join('swift'), dst.join('swift')
      )
      if self.m.path.exists(dst.join('swift-5.0')):
        self.m.file.rmtree('Delete swift-5.0', dst.join('swift-5.0'))
      self.m.file.copytree(
          'Copy swift-5.0', swift_path.join('swift-5.0'), dst.join('swift-5.0')
      )
      self.m.file.listdir('List directory', dst)

  def gems(self, env, env_prefixes, gemfile_dir):
    """Installs android sdk.

    Args:
      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
      gemfile_dir(Path): The path to the location of the repository gemfile.
    """
    deps_list = self.m.properties.get('dependencies', [])
    deps = [d['dependency'] for d in deps_list]
    if 'gems' not in deps:
      # Noop if gems property is not set.
      return

    gem_file = self.m.path['start_dir'].join('flutter', 'flutter')
    gem_dir = self.m.path['start_dir'].join('gems')
    with self.m.step.nest('Install gems'):
      self.m.file.ensure_directory('mkdir gems', gem_dir)
      # Temporarily install bundler
      with self.m.context(cwd=gem_dir):
        self.m.step(
            'install bundler',
            ['gem', 'install', 'bundler', '--install-dir', '.']
        )
      env['GEM_HOME'] = gem_dir
      paths = env_prefixes.get('PATH', [])
      temp_paths = copy.deepcopy(paths)
      temp_paths.append(gem_dir.join('bin'))
      env_prefixes['PATH'] = temp_paths
      with self.m.context(env=env, env_prefixes=env_prefixes, cwd=gemfile_dir):
        self.m.step(
            'set gems path', ['bundle', 'config', 'set', 'path', gem_dir]
        )
        self.m.step('install gems', ['bundler', 'install'])
      # Update envs to the final destination.
      self.m.file.listdir('list bundle', gem_dir, recursive=True)
      env['GEM_HOME'] = gem_dir.join('ruby', '2.6.0')
      paths.append(gem_dir.join('ruby', '2.6.0', 'bin'))
      env_prefixes['PATH'] = paths
