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
        'https://github.com/flutter/packages',
}

from recipe_engine import recipe_api


class RepoUtilApi(recipe_api.RecipeApi):
  """Provides utilities to work with flutter repos."""

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

    git_url = url or REPOS[name]
    git_ref = ref or self.m.buildbucket.gitiles_commit.ref
    return self.m.git.checkout(
        git_url,
        dir_path=checkout_path,
        ref=git_ref,
        recursive=True,
        set_got_revision=True,
        tags=True)

  def flutter_environment(self, checkout_path):
    """Returns env and env_prefixes of an flutter/dart command environment."""
    dart_bin = checkout_path.join('bin', 'cache', 'dart-sdk', 'bin')
    flutter_bin = checkout_path.join('bin')
    # Fail if dart and flutter bin folders do not exist.
    if not (self.m.path.exists(dart_bin) and self.m.path.exists(flutter_bin)):
      msg = ('dart or flutter bin folders do not exist,'
             'did you forget to checkout flutter repo?')
      self.m.python.failing_step('Flutter Environment', msg)

    env = {
        # Setup our own pub_cache to not affect other slaves on this machine,
        # and so that the pre-populated pub cache is contained in the package.
        'PUB_CACHE': checkout_path.join('.pub-cache'),
        # Windows Packaging script assumes this is set.
        'DEPOT_TOOLS': str(self.m.depot_tools.root),
    }
    env_prefixes = {'PATH': [flutter_bin, dart_bin]}
    return env, env_prefixes
