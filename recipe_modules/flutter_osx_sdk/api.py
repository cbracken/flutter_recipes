# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager, nested
from recipe_engine import recipe_api


class FlutterXcodeApi(recipe_api.RecipeApi):

  def __init__(self, sdk_properties, *args, **kwargs):
    super(FlutterXcodeApi, self).__init__(*args, **kwargs)

  @contextmanager
  def __call__(self, kind):
    if self.m.platform.is_mac:
      with self.m.osx_sdk(kind):
        yield
    else:
      yield

