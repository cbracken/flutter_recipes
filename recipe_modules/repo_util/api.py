# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FLUTTER_REPO = 'https://chromium.googlesource.com/external/github.com/flutter/flutter'
ENGINE_REPO = 'https://chromium.googlesource.com/external/github.com/flutter/engine'
COCOON_REPO = 'https://chromium.googlesource.com/external/github.com/flutter/cocoon'

from recipe_engine import recipe_api


class RepoUtilApi(recipe_api.RecipeApi):
  """Provides utilities to work with flutter repos."""

  def checkout_flutter(self, checkout_path, url=None, ref=None):
    git_url = url or FLUTTER_REPO
    git_ref = ref or self.m.buildbucket.gitiles_commit.ref
    return self.m.git.checkout(
        git_url, ref=git_ref, recursive=True, set_got_revision=True, tags=True)

  def checkout_engine(self, checkout_path, url=None, ref=None):
    git_url = url or ENGINE_REPO
    git_ref = ref or self.m.buildbucket.gitiles_commit.ref
    return self.m.git.checkout(
        git_url, ref=git_ref, recursive=True, set_got_revision=True, tags=True)

  def checkout_cocoon(self, checkout_path, url=None, ref=None):
    git_url = url or COCOON_REPO
    git_ref = ref or self.m.buildbucket.gitiles_commit.ref
    return self.m.git.checkout(
        git_url, ref=git_ref, recursive=True, set_got_revision=True, tags=True)

  def flutter_environment(self, checkout_path):
    dart_bin = checkout_path.join('bin', 'cache', 'dart-sdk', 'bin')
    flutter_bin = checkout_path.join('bin')
    path_prefixes = [
        flutter_bin,
        dart_bin,
    ]
    # Fail if dart and flutter bin folders do not exist.
    if not (self.m.path.exists(dart_bin) and self.m.path.exists(flutter_bin)):
      msg = ('dart or flutter bin folders do not exist,'
             'did you forget to checkout flutter repo?')
      self.m.python.failing_step('Flutter Environment', msg)
    env_prefixes = {'PATH': path_prefixes}
    pub_cache = checkout_path.join('.pub-cache')
    env = {
        # Setup our own pub_cache to not affect other slaves on this machine,
        # and so that the pre-populated pub cache is contained in the package.
        'PUB_CACHE': pub_cache,
        # Windows Packaging script assumes this is set.
        'DEPOT_TOOLS': str(self.m.depot_tools.root),
    }
    return env, env_prefixes
