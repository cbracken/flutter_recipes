# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
  'goma',
  'recipe_engine/properties',
]


def RunSteps(api):
  client_type = api.m.properties.get('client_type')
  additional_platforms = api.m.properties.get('additional_platforms')
  ephemeral = api.m.properties.get('ephemeral')
  api.goma.ensure_goma(client_type=client_type, additional_platforms=additional_platforms, ephemeral=ephemeral)
  if additional_platforms:
    api.goma.additional_goma_dir(additional_platforms[0])


def GenTests(api):
  yield api.test(
      'non_canary',
      api.properties(client_type='release'),
  )
  yield api.test(
      'canary',
      api.properties(client_type='candidate'),
  )
  yield api.test(
      'latest',
      api.properties(client_type='latest'),
  )
  yield api.test(
      'additional_canary',
      api.properties(client_type='candidate'),
      api.properties(additional_platforms=['chromeos-amd64']),
  )
  yield api.test(
      'ephemeral',
      api.properties(ephemeral=True),
  )
