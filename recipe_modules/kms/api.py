# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class KMSApi(recipe_api.RecipeApi):
  """Provides KMS support for recipe secrets."""

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
        self.m.cipd.EnsureFile().add_package(cloudkms_package, 'latest')
    )
    encrypt_file = self.m.path['cleanup'].join(input_file)
    self.m.gsutil.download('flutter_configs', input_file, encrypt_file)
    cloudkms = cloudkms_dir.join(
        'cloudkms.exe' if self.m.platform.name == 'win' else 'cloudkms'
    )
    self.m.step(
        'cloudkms get key', [
            cloudkms, 'decrypt', '-input', encrypt_file, '-output', secret_path,
            'projects/flutter-infra/locations/global'
            '/keyRings/luci/cryptoKeys/flutter-infra'
        ]
    )

  def decrypt_secrets(self, env, secrets):
    """Decrypts the secrets.

    This method decrypts files stored in GCS using kms certificates and sets
    environment variables pointing to the location of the decrypted file. You
    have to be careful of not printing the content of the decrypted file or
    adding the content of the decrypted file as an environment variable as it
    will print in the logs.

    Args:
      env(dict): Current environment variables.
      secrets(dict): The key is the n. me of the env variable referencing the
        decrypted file and the value is the path to the encrypted file in gcs.
    """
    for k, v in secrets.items():
      secret_path = self.m.path['cleanup'].join(k)
      self.m.kms.get_secret(v, secret_path)
      env[k] = secret_path
