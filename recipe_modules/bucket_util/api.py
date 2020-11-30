# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from recipe_engine import recipe_api

INFRA_BUCKET_NAME = 'flutter_infra'

class BucketUtilApi(recipe_api.RecipeApi):
  """Utility functions to upload files to cloud buckets.

  Properties:
    upload_packages: (bool) Whether to upload the packages to the bucket.
    force_upload:
      (bool) Whether a file should be re-uploaded if it exists in the bucket.
  """

  def should_upload_packages(self):
    return self.m.properties.get('upload_packages', False)

  def upload_folder(self,
                    dir_label,
                    parent_directory,
                    folder_name,
                    zip_name,
                    platform=None):
    """Uploads a folder to the cloud bucket

    Args:
      dir_label: (str) A label to append to the step that creates a temporary directory.
      parent_directory: (str) Parent directory of folder_name.
      folder_name: (str) Folder to upload.
      zip_name: (str) Name of the zip file in the cloud bucket.
      platform: (str) Directory name to add the zip file to.
    """
    self.upload_folder_and_files(dir_label,
                                 parent_directory,
                                 folder_name,
                                 zip_name,
                                 platform=platform)

  def upload_folder_and_files(self,
                              dir_label,
                              parent_directory,
                              folder_name,
                              zip_name,
                              platform=None,
                              file_paths=None):
    """Uploads a folder and or files to the cloud bucket

    Args:
      dir_label: (str) A label to append to the step that creates a temporary directory.
      parent_directory: (str) Parent directory of folder_name and/or file_paths.
      folder_name: (str) Folder to upload.
      zip_name: (str) Name of the zip file in the cloud bucket.
      platform: (str) directory name to add the zip file to.
      file_paths: (list) A list of string with the filenames to upload.
    """
    with self.m.os_utils.make_temp_directory(dir_label) as temp_dir:
      remote_name = '%s/%s' % (platform, zip_name) if platform else zip_name
      local_zip = temp_dir.join(zip_name)
      remote_zip = self.get_cloud_path(remote_name)
      parent_directory = self.m.path['cache'].join('builder', parent_directory)
      pkg = self.m.zip.make_package(parent_directory, local_zip)
      pkg.add_directory(parent_directory.join(folder_name))

      if file_paths is not None:
        self.add_files(pkg, file_paths)

      pkg.zip('Zip %s' % folder_name)
      if self.should_upload_packages():
        self.safe_upload(local_zip, remote_zip)

  def safe_upload(self,
                  local_path,
                  remote_path,
                  bucket_name=INFRA_BUCKET_NAME,
                  args=[],
                  skip_on_duplicate=False):
    """Upload a file if it doesn't already exist, fail job otherwise.

    The check can be overridden with the `force_upload` property.

    Args:
      local_path: (str) The local path to upload.
      remote_path: (str) The remove path in the cloud bucket.
      bucket_name: (str) The bucket name. Defaults to flutter_infra.
      args: (list) Arguments to pass to gsutil.upload step.
      skip_on_duplicate: (bool)
        Whether to avoid uploading to an already existing path in the bucket.

    Returns:
      The result of the gsutil.upload step. Useful for verifying the exit code.
    """
    assert (self.should_upload_packages())

    experimental = self.m.runtime.is_experimental
    force_upload = self.m.properties.get('force_upload', False)
    # Experimental builds go to a different bucket, duplicates allowed
    if not experimental and not force_upload:
      cloud_path = 'gs://%s/%s' % (bucket_name, remote_path)
      result = self.m.step(
          'Ensure %s does not already exist on cloud storage' % remote_path, [
              'python',
              self.m.depot_tools.gsutil_py_path,
              'stat',
              cloud_path,
          ],
          ok_ret='all')
      # A return value of 0 means the file ALREADY exists on cloud storage
      if result.exc_result.retcode == 0:
        if skip_on_duplicate:
          # This file already exists, but we shouldn't fail the build
          return
        raise AssertionError('%s already exists on cloud storage' % cloud_path)

    return self.m.gsutil.upload(
        local_path,
        bucket_name,
        remote_path,
        args=args,
        name='upload "%s"' % remote_path)

  def add_files(self, pkg, relative_paths=[]):
    """Adds files to the package.

    Args:
      pkg: (package) The package that contains the files.
      relative_paths:
        (list) The relative_paths parameter is a list of strings and pairs of
        strings. If the path is a string, then it will be used as the source
        filename, and its basename will be used as the destination filename
        in the archive. If the path is a pair, then the first element will be
        used as the source filename, and the second element will be used as the
        destination filename in the archive.
    """
    for path in relative_paths:
      pkg.add_file(pkg.root.join(path),
                   archive_name=self.m.path.basename(path))

  def add_directories(self, pkg, relative_paths=[]):
    """Adds directories to the package.

    Args:
      pkg: (package) The package that contains the files.
      relative_paths:
        (list) The relative_paths parameter is a list of directories to add to
        the archive.
    """
    for path in relative_paths:
      pkg.add_directory(pkg.root.join(path))

  def get_cloud_path(self, path):
    """Gets the path in the cloud bucket.

    Args:
      path: (str) Path to append after the commit hash.

    Returns:
      The path formed by `flutter/<commit-hash>/<path>`.
    """
    git_hash = self.m.buildbucket.gitiles_commit.id
    if self.m.runtime.is_experimental:
      return 'flutter/experimental/%s/%s' % (git_hash, path)
    return 'flutter/%s/%s' % (git_hash, path)
