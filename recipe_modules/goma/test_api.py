# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_test_api


class GomaTestApi(recipe_test_api.RecipeTestApi):
  def __call__(self, jobs=80, debug=False, enable_ats=False, server_host="",
               rpc_extra_params=""):
    """Simulate pre-configured Goma through properties."""
    assert isinstance(jobs, int), '%r (%s)' % (jobs, type(jobs))
    ret = self.test(None)
    ret.properties = {
      '$flutter/goma': {
        'jobs': jobs,
        'enable_ats': enable_ats,
        'server_host': server_host,
        'rpc_extra_params': rpc_extra_params,
      },
    }
    if debug:
      ret.properties['$flutter/goma']['debug'] = True
    return ret
