# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPS = [
    'bucket_util',
    'recipe_engine/properties',
    'recipe_engine/runtime',
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
      'test2.zip',  # zip_name
      file_paths=['a.txt'])

  api.bucket_util.upload_folder_and_files(
      'Upload test.zip', # dir_label
      'src', # parent_directory
      'build', # folder_name
      'test3.zip', # zip_name
      platform='parent_directory',
      file_paths=['a.txt'])

  if api.bucket_util.should_upload_packages():
    api.bucket_util.safe_upload(
                    "foo", # local_path
                    "bar", # remote_path
                    skip_on_duplicate=True)


def GenTests(api):
  yield api.test(
      'basic',
      api.properties(
          upload_packages=False,
      ),
  )
  yield api.test(
      'upload_packages',
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
      'upload_packages_tiggers_exception_and_package_exists',
      api.properties(
          upload_packages=True,
      ),
      api.expect_exception('AssertionError'),
  )
  yield api.test(
      'upload_packages_experimental_runtime',
      api.runtime(is_luci=True, is_experimental=True),
      api.properties(
          upload_packages=True,
      ),
  )
