# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api


class FirebaseApi(recipe_api.RecipeApi):
  """Provides utilities to upload docs to Firebase.

  This API only works on Linux machines.
  """

  def deploy_docs(self, env, env_prefixes, docs_path, project):
    """Deploys docs to Firebase.

    Args:
      env(dict): Current environment variables.
      env_prefixes(dict):  Current environment prefixes variables.
      docs_path(Path): A path with the directory containing the docs to
        upload.
      project(str): A string with the firebase project where docs will be
        uploaded.
    """
    service_account = self.m.service_account.default()
    access_token = service_account.get_access_token(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    access_token_path = self.m.path.mkstemp()
    self.m.file.write_text(
        "write token", access_token_path, access_token, include_log=False
    )
    env['TOKEN_PATH'] = access_token_path
    env['GCP_PROJECT'] = project
    with self.m.step.nest('Deploy docs'):
      with self.m.context(env=env, env_prefixes=env_prefixes, cwd=docs_path):
        resource_name = self.resource('firebase_deploy.sh')
        self.m.step('Set execute permission', ['chmod', '755', resource_name])
        self.m.step('Firebase deploy', [resource_name])
