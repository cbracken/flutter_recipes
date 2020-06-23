# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

class KMSApi(recipe_api.RecipeApi):
  """Provides KMS support for recipe secretes."""
  def get_secret(self, input_file, secret_path):
    """Decrypts the encrypted secret.

    Args:
      input_file (str): encrypted file of the secret.
      secret_path (Path): path of decrypted secret.
    """
    cloudkms_dir = self.m.path['start_dir'].join('cloudkms')
    cloudkms_package = 'infra/tools/luci/cloudkms/${platform}'
    self.m.cipd.ensure(
        cloudkms_dir,
        self.m.cipd.EnsureFile().add_package(cloudkms_package, 'latest'))
    encrypt_file = self.m.path['cleanup'].join(input_file)
    self.m.gsutil.download('flutter_configs', input_file, encrypt_file)
    cloudkms = cloudkms_dir.join('cloudkms.exe' if self.m.platform.name == 'win' else 'cloudkms')
    self.m.step('cloudkms get key', [
        cloudkms, 'decrypt', '-input', encrypt_file, '-output', secret_path,
        'projects/flutter-infra/locations/global'
        '/keyRings/luci/cryptoKeys/flutter-infra'
    ])