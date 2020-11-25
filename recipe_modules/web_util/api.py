# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import copy
from recipe_engine import recipe_api


class WebUtilsApi(recipe_api.RecipeApi):
  """Utilities to use when running flutter web engine tests."""

  def firefox_driver(self, checkout):
    """Downloads the latest version of the Firefox web driver from CIPD."""
    # Download the driver for Firefox.
    firefox_driver_path = checkout.join('flutter', 'lib', 'web_ui',
                                        '.dart_tool', 'drivers', 'firefox')
    pkgdriver = self.m.cipd.EnsureFile()
    pkgdriver.add_package(
        'flutter_internal/browser-drivers/firefoxdriver-linux', 'latest')
    self.m.cipd.ensure(firefox_driver_path, pkgdriver)

  def chrome(self, checkout):
    """Downloads Chrome from CIPD.

    The chrome version to be used will be read from a file on the repo side.
    """
    browser_lock_yaml_file = checkout.join('flutter', 'lib', 'web_ui', 'dev',
                                           'browser_lock.yaml')
    with self.m.context(cwd=checkout):
      result = self.m.yaml.read(
          'read browser lock yaml',
          browser_lock_yaml_file,
          self.m.json.output(),
      )
      browser_lock_content = result.json.output
      platform = self.m.platform.name.capitalize()
      binary = browser_lock_content['chrome'][platform]
      chrome_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                  'chrome', '%s' % binary)
    # Using the binary number since the repos side file uses binary names.
    # See: flutter/engine/blob/master/lib/web_ui/dev/browser_lock.yaml
    # Chrome also uses these binary numbers for archiving different versions.
    chrome_pkg = self.m.cipd.EnsureFile()
    chrome_pkg.add_package('flutter_internal/browsers/chrome/${platform}',
                           binary)
    self.m.cipd.ensure(chrome_path, chrome_pkg)

  def chrome_driver(self, checkout):
    """Downloads Chrome web driver from CIPD.

    The driver version to be used will be read from a file on the repo side.
    """
    # Get driver version from the engine repo.
    # See: flutter/engine/blob/master/lib/web_ui/dev/browser_lock.yaml
    browser_lock_yaml_file = checkout.join('flutter', 'lib', 'web_ui', 'dev',
                                           'browser_lock.yaml')
    with self.m.context(cwd=checkout):
      result = self.m.yaml.read(
          'read browser lock yaml',
          browser_lock_yaml_file,
          self.m.json.output(),
      )
      browser_lock_content = result.json.output
      version = browser_lock_content['required_driver_version']['chrome']
    chrome_driver_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                       'drivers', 'chrome', '%s' % version)
    chrome_pkgdriver = self.m.cipd.EnsureFile()
    chrome_pkgdriver.add_package(
        'flutter_internal/browser-drivers/chrome/${platform}',
        'latest-%s' % version)
    self.m.cipd.ensure(chrome_driver_path, chrome_pkgdriver)

  def clone_goldens_repo(self, checkout):
    """Clone the repository that keeps golden files.

    The repository name and the reference SHA will be read from a file on the
    repo side.
    """
    builder_root = self.m.path['cache'].join('builder')
    goldens = builder_root.join('goldens')
    self.m.file.ensure_directory('mkdir goldens', goldens)
    golden_yaml_file = checkout.join('flutter', 'lib', 'web_ui', 'dev',
                                     'goldens_lock.yaml')
    with self.m.context(cwd=builder_root):
      # Use golden_lock.yaml file to read url of the goldens repository and
      # the revision number to checkout.
      # https://github.com/flutter/engine/blob/master/lib/web_ui/dev/goldens_lock.yaml
      # This file is used by web engine developers. The engine developers update
      # the flutter/goldens.git repo when they  need changes. Later change the
      # revision number on this file.
      result = self.m.yaml.read(
          'read yaml',
          golden_yaml_file,
          self.m.json.output(),
      )
      # The content of the file is expected to be:
      #
      # repository: https://github.com/flutter/goldens.git
      # revision: b6efc75885c23f0b5c485d8bd659ed339feec9ec
      golden_lock_content = result.json.output
      repo = golden_lock_content['repository']
      revision_number = golden_lock_content['revision']
    with self.m.context(cwd=goldens):
      self.m.git.checkout(
          repo,
          dir_path=goldens,
          ref=revision_number,
          recursive=True,
          set_got_revision=True)
    golden_files = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                                 'goldens')
    self.m.file.copytree('copy goldens', goldens, golden_files)

  def upload_failing_goldens(self, checkout, browser):
    """Upload the failed goldens files to a gcs bucket.

    Parse the logs to determine which golden tests are failed. Upload expected
    and actual golden files to a gcs bucket. Display links to html pages where
    developer can compare actual vs expected images.
    """
    logs_path = checkout.join('flutter', 'lib', 'web_ui', '.dart_tool',
                              'test_results')
    tests_info_file_path = logs_path.join('info.txt')
    self.m.file.write_text(
        'write info file',
        tests_info_file_path,
        'tests for %s' % self.m.platform.name,
        'tests for windows',
    )

    if not self.m.properties.get(
        'gcs_goldens_bucket') or self.m.runtime.is_experimental:
      # This is to avoid trying to upload files when 'gcs_goldens_bucket' is
      # missing or when running from led.
      return

    bucket_id = self.m.buildbucket.build.id
    self.m.gsutil.upload(
        bucket=self.m.properties['gcs_goldens_bucket'],
        source=logs_path,
        dest='%s/%s/%s' % ('web_engine', bucket_id, browser),
        link_name='archive goldens',
        args=['-r'],
        multithreaded=True,
        name='upload goldens %s' % bucket_id,
        unauthenticated_url=True)
    html_files = self.m.file.glob_paths(
        'html goldens',
        source=logs_path,
        pattern='*.html',
        test_data=['a.html'])
    with self.m.step.nest('Failed golden links') as presentation:
      for html_file in html_files:
        base_name = self.m.path.basename(html_file)
        url = 'https://storage.googleapis.com/%s/web_engine/%s/%s/%s' % (
            self.m.properties['gcs_goldens_bucket'], bucket_id, browser,
            base_name)
        presentation.links[base_name] = url

  def prepare_dependencies(self, checkout):
    """Install all the required dependencies for a given felt test."""
    deps = self.m.properties.get('dependencies', [])
    available_deps = {
        'chrome': self.chrome,
        'chrome_driver': self.chrome_driver,
        'firefox_driver': self.firefox_driver,
        'goldens_repo': self.clone_goldens_repo,
    }
    for dep in deps:
      dep_funct = available_deps.get(dep)
      if not dep_funct:
        raise ValueError('Dependency %s not available.' % dep)
      dep_funct(checkout)
