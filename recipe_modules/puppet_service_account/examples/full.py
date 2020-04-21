# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Small example of using the puppet_service_account api."""

DEPS = [
  'puppet_service_account',
  'recipe_engine/platform',
]


def RunSteps(api):
  # Fetch a token directly via puppet_service_account.get_access_token().
  token1 = api.puppet_service_account.get_access_token('fake-account')
  # Fetch another token by first creating a service_account.ServiceAccount
  # instance and using its get_access_token().
  token2 = api.puppet_service_account.get('fake-account').get_access_token()
  assert token1 == token2


def GenTests(api):
  yield api.test('mac_pre_catalina') + api.platform(
      'mac', 64, mac_release='10.14.0')
  yield api.test('mac_post_catalina') + api.platform(
      'mac', 64, mac_release='10.15.0')
  yield api.test('linux') + api.platform('linux', 64)
  yield api.test('win') + api.platform('win', 64)
