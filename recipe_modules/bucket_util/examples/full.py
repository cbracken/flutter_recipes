# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'bucket_util',
    'recipe_engine/properties',
]


def RunSteps(api):
  api.bucket_util.upload_folder(
      'Upload test.zip', # dir_label
      'src', # parent_directory
      'build', # folder_name
      'test1.zip') # zip_name

  api.bucket_util.upload_folder_and_files(
      'Upload test.zip', # dir_label
      'src', # parent_directory
      'build', # folder_name
      ['a.txt'], # file_paths
      'test2.zip') # zip_name

  api.bucket_util.upload_folder_and_files(
      'Upload test.zip', # dir_label
      'src', # parent_directory
      'build', # folder_name
      ['a.txt'], # file_paths
      'test3.zip', # zip_name
      'parent_directory') # platform

  if api.bucket_util.should_upload_packages():
    api.bucket_util.safe_upload(
                    "foo", # local_path
                    "bar", # remote_path
                    skip_on_duplicate=True)


def GenTests(api):
  yield api.test(
      'test 1 (upload_packages=False)',
      api.properties(
          upload_packages=False,
      ),
  )
  yield api.test(
      'test 2 (upload_packages=True)',
      api.properties(
          upload_packages=True,
      ),
      api.step_data(
          'Ensure flutter//test1.zip does not already exist on cloud storage',
          retcode=1,
      ),
      api.step_data(
          'Ensure flutter//test2.zip does not already exist on cloud storage',
          retcode=1,
      ),
      api.step_data(
          'Ensure flutter//parent_directory/test3.zip does not already exist on cloud storage',
          retcode=1,
      ),
  )
  yield api.test(
      'test 3 (upload_packages=True)',
      api.properties(
          upload_packages=True,
      ),
      api.expect_exception('AssertionError'),
  )
