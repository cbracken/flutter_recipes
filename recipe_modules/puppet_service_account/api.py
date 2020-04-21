# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""**[DEPRECATED]** API for generating OAuth2 access tokens from service account
keys predeployed to Chrome Ops bots via Puppet.

Depends on 'luci-auth' being in PATH.

This module exists only to support Buildbot code. On LUCI use default account
exposed through 'recipe_engine/service_account' module.
"""

from recipe_engine import recipe_api


class PuppetServiceAccountApi(recipe_api.RecipeApi):
  @property
  def keys_path(self):
    """Path to a directory where ChromeOps Puppet drops service account keys."""
    if self.m.platform.is_win:
      return 'C:\\creds\\service_accounts'

    if self.m.platform.is_mac:
      # Starting with macOS 10.15 (Catalina), Puppet stores the service
      # accounts in /opt/creds instead of /creds.
      if self.m.platform.mac_release >= self.m.version.parse('10.15'):
        return '/opt/creds/service_accounts'

    return '/creds/service_accounts'

  def get(self, account):
    """Returns a recipe_module.service_account.ServiceAccount for the account.

    Assumes a service account key for the given account is available at
    self.keys_path.

    Args:
      account: a name of the service account, as defined in Puppet config.
    Returns
      A recipe_module.service_account.ServiceAccount instance.
    """
    return self.m.service_account.from_credentials_json(
        self.get_key_path(account))

  def get_key_path(self, account):
    """Path to a particular JSON key (as str)."""
    return self.m.path.join(self.keys_path, 'service-account-%s.json' % account)

  def get_access_token(self, account, scopes=None):
    """Returns an access token for a service account.

    Token's lifetime is guaranteed to be at least 3 minutes and at most 45.

    Args:
      account: a name of the service account, as defined in Puppet config.
      scopes: list of OAuth scopes for new token, default is [userinfo.email].
    """
    return self.m.service_account.from_credentials_json(
        self.get_key_path(account)).get_access_token(scopes)
