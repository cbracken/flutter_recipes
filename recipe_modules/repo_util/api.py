# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

REPOS = {
    'flutter':
        'https://chromium.googlesource.com/external/github.com/flutter/flutter',
    'engine':
        'https://chromium.googlesource.com/external/github.com/flutter/engine',
    'cocoon':
        'https://chromium.googlesource.com/external/github.com/flutter/cocoon',
    'packages':
        'https://github.com/flutter/packages', 'plugins':
            'https://github.com/flutter/plugins'
}

import re
from recipe_engine import recipe_api


class RepoUtilApi(recipe_api.RecipeApi):
  """Provides utilities to work with flutter repos."""

  def engine_checkout(self, checkout_path, env, env_prefixes, clobber=True):
    """Checkout code using gclient.

    Args:
      checkout_path(Path): The path to checkout source code and dependencies.
      env(dict): A dictionary with the environment variables to set.
      env(dict): A dictionary with the paths to be added to environment variables.
      clobber(bool): A boolean indicating whether the checkout folder should be cleaned.
    """
    git_url = REPOS['engine']
    git_id = self.m.buildbucket.gitiles_commit.id
    git_ref = self.m.buildbucket.gitiles_commit.ref
    if 'git_url' in self.m.properties and 'git_ref' in self.m.properties:
      git_url = self.m.properties['git_url']
      git_id = self.m.properties['git_ref']
      git_ref = self.m.properties['git_ref']

    # Inner function to execute code a second time in case of failure.
    def _InnerCheckout():
      with self.m.context(env=env, env_prefixes=env_prefixes,
                          cwd=checkout_path), self.m.depot_tools.on_path():
        src_cfg = self.m.gclient.make_config()
        soln = src_cfg.solutions.add()
        soln.name = 'src/flutter'
        soln.url = git_url
        soln.revision = git_id
        src_cfg.parent_got_revision_mapping['parent_got_revision'
                                           ] = 'got_revision'
        src_cfg.repo_path_map[git_url] = ('src/flutter', git_ref)
        self.m.gclient.c = src_cfg
        self.m.gclient.c.got_revision_mapping['src/flutter'
                                             ] = 'got_engine_revision'
        self.m.bot_update.ensure_checkout()
        self.m.gclient.runhooks()

    with self.m.step.nest('Checkout source code'):
      try:
        # Run this out of context
        if clobber:
          self.m.file.rmtree('Clobber cache', checkout_path)
          self.m.file.ensure_directory('Ensure checkout cache', checkout_path)
        _InnerCheckout()
      except (self.m.step.StepFailure, self.m.step.InfraFailure):
        # Run this out of context

        # Ensure depot tools is in the path to prevent problems with vpython not
        # being found after a failure.
        with self.m.depot_tools.on_path():
          self.m.file.rmtree('Clobber cache', checkout_path)
          self.m.file.rmtree(
              'Clobber git cache', self.m.path['cache'].join('git')
          )
          self.m.file.ensure_directory('Ensure checkout cache', checkout_path)
        # Now try a second time
        _InnerCheckout()

  def checkout(self, name, checkout_path, url=None, ref=None):
    """Checks out a repo and returns sha1 of checked out revision.

    The supproted repository names and their urls are defined in the global
    REPOS variable.

    Args:
      name (str): name of the supported repository.
      checkout_path (Path): directory to clone into.
      url (str): optional url overwrite of the remote repo.
      ref (str): optional ref overwrite to fetch and check out.
    """
    if name not in REPOS:
      raise ValueError('Unsupported repo: %s' % name)
    with self.m.step.nest('Checkout flutter/%s' % name):
      git_url = url or REPOS[name]
      # gitiles_commit.id is more specific than gitiles_commit.ref, which is
      # branch
      git_ref = ref or self.m.buildbucket.gitiles_commit.id
      return self.m.git.checkout(
          git_url,
          dir_path=checkout_path,
          ref=git_ref,
          recursive=True,
          set_got_revision=True,
          tags=True
      )

  def flutter_environment(self, checkout_path):
    """Returns env and env_prefixes of an flutter/dart command environment."""
    dart_bin = checkout_path.join('bin', 'cache', 'dart-sdk', 'bin')
    flutter_bin = checkout_path.join('bin')
    # Fail if flutter bin folder does not exist. dart-sdk/bin folder will be
    # available only after running "flutter doctor" and it needs to be run as
    # the first command on the context using the environment.
    if not self.m.path.exists(flutter_bin):
      msg = (
          'flutter bin folders do not exist,'
          'did you forget to checkout flutter repo?'
      )
      self.m.python.failing_step('Flutter Environment', msg)
    git_ref = self.m.properties.get('git_ref', '')
    pub_cache_path = (self.m.path['cache'].join('.pub-cache') if self.m.platform.is_mac
                      else self.m.path['start_dir'].join('.pub-cache'))
    env = {
        # Setup our own pub_cache to not affect other slaves on this machine,
        # and so that the pre-populated pub cache is contained in the package.
        'PUB_CACHE': pub_cache_path,
        # Windows Packaging script assumes this is set.
        'DEPOT_TOOLS':
            str(self.m.depot_tools.root),
        'SDK_CHECKOUT_PATH':
            checkout_path,
        'LUCI_CI':
            True,
        'LUCI_PR':
            re.sub('refs\/pull\/|\/head', '', git_ref),
        'LUCI_BRANCH':
            self.m.properties.get('release_ref', '').replace('refs/heads/', ''),
        'OS':
            'linux' if self.m.platform.name == 'linux' else
            ('darwin' if self.m.platform.name == 'mac' else 'win')
    }
    env_prefixes = {'PATH': ['%s' % str(flutter_bin), '%s' % str(dart_bin)]}
    return env, env_prefixes

  def sdk_checkout_path(self):
    """Returns the checkoout path of the current flutter_environment.

    Returns(Path): A path object with the current checkout path.
    """
    checkout_path = self.m.context.env.get('SDK_CHECKOUT_PATH')
    assert checkout_path, 'Outside of a flutter_environment?'
    return self.m.path.abs_to_path(checkout_path)
