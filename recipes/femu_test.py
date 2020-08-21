# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from contextlib import contextmanager

from PB.recipes.flutter.engine import InputProperties
from PB.recipes.flutter.engine import EnvProperties

from PB.go.chromium.org.luci.buildbucket.proto import build as build_pb2
from google.protobuf import struct_pb2

import re

DEPS = [
    'fuchsia/goma',
    'depot_tools/depot_tools',
    'flutter/repo_util',
    'fuchsia/display_util',
    'fuchsia/sdk',
    'fuchsia/ssh',
    'fuchsia/vdl',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/isolated',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/properties',
    'recipe_engine/raw_io',
    'recipe_engine/step',
    'recipe_engine/swarming',
]

PROPERTIES = InputProperties
ENV_PROPERTIES = EnvProperties


def GetCheckoutPath(api):
  return api.path['cache'].join('builder', 'src')


def Build(api, config, *targets):
  checkout = GetCheckoutPath(api)
  build_dir = checkout.join('out/%s' % config)
  goma_jobs = api.properties['goma_jobs']
  ninja_args = [api.depot_tools.ninja_path, '-j', goma_jobs, '-C', build_dir]
  ninja_args.extend(targets)
  with api.goma.build_with_goma():
    name='build %s' % ' '.join([config] + list(targets))
    api.step(name, ninja_args)


def GetFlutterFuchsiaBuildTargets(product, include_test_targets=False):
  targets = ['flutter/shell/platform/fuchsia:fuchsia']
  if include_test_targets:
    targets += ['fuchsia_tests']
  return targets


def BuildAndTestFuchsia(api, build_script, git_rev):
  RunGN(api, '--fuchsia', '--fuchsia-cpu', 'x64', '--runtime-mode', 'debug',
        '--no-lto')
  Build(api, 'fuchsia_debug_x64', *GetFlutterFuchsiaBuildTargets(False, True))
  fuchsia_package_cmd = [
      'python', build_script, '--engine-version', git_rev, '--skip-build',
      '--archs', 'x64', '--runtime-mode', 'debug'
  ]
  api.step('Package Fuchsia Artifacts', fuchsia_package_cmd)
  TestFuchsiaFEMU(api)


def RunGN(api, *args):
  checkout = GetCheckoutPath(api)
  gn_cmd = ['python', checkout.join('flutter/tools/gn'), '--goma']
  gn_cmd.extend(args)
  api.step('gn %s' % ' '.join(args), gn_cmd)


def GetFuchsiaBuildId(api):
  checkout = GetCheckoutPath(api)
  manifest_path = checkout.join('fuchsia', 'sdk', 'linux', 'meta',
                                'manifest.json')
  manifest_data = api.file.read_json('Read manifest', manifest_path)
  return manifest_data['id']


# TODO(yuanzhi) Move this logic to vdl recipe_module
def IsolateSymlink(api):
  """Create an isolate containing flutter test components and fuchsia runfiles for FEMU."""
  sdk_version = GetFuchsiaBuildId(api)
  checkout = GetCheckoutPath(api)
  root_dir = api.path.mkdtemp('vdl_runfiles_')
  isolate_tree = api.file.symlink_tree(root=root_dir)
  flutter_tests = []

  def add(src, name_rel_to_root):
    isolate_tree.register_link(
        target=src,
        linkname=isolate_tree.root.join(name_rel_to_root),
    )

  def addVDLFiles():
    api.vdl.set_vdl_cipd_tag(tag="g3-revision:vdl_fuchsia_20200811_RC00")
    add(api.vdl.vdl_path, 'device_launcher')
    api.vdl.set_aemu_cipd_tag(tag="git_revision:b14d86bbed0c1c64e9d177daa981e9c3a7df8cba")
    add(api.vdl.aemu_dir, 'aemu')
    add(api.vdl.create_device_proto(), 'virtual_device.textproto')

  def addPackageFiles():
    fuchsia_packages = api.vdl.get_package_paths(sdk_version=sdk_version)
    add(fuchsia_packages.pm, api.path.basename(fuchsia_packages.pm))
    add(fuchsia_packages.tar_file, "package_archive")
    add(fuchsia_packages.amber_files,
        api.path.basename(fuchsia_packages.amber_files))

  def addImageFiles():
    ssh_files = api.vdl.gen_ssh_files()
    add(ssh_files.id_public, api.path.basename(ssh_files.id_public))
    add(ssh_files.id_private, api.path.basename(ssh_files.id_private))

    fuchsia_images = api.vdl.get_image_paths(sdk_version=sdk_version)
    add(fuchsia_images.build_args, "qemu_buildargs")
    add(fuchsia_images.kernel_file, "qemu_kernel")
    add(fuchsia_images.system_fvm, "qemu_fvm")
    add(api.sdk.sdk_path.join("tools", "far"), "far")
    add(api.sdk.sdk_path.join("tools", "fvm"), "fvm")

    ## Provision and add zircon-a
    authorized_zircona = api.buildbucket.builder_cache_path.join(
        'zircon-authorized.zbi')
    api.sdk.authorize_zbi(
        ssh_key_path=ssh_files.id_public,
        zbi_input_path=fuchsia_images.zircona,
        zbi_output_path=authorized_zircona,
    )
    add(authorized_zircona, "qemu_zircona-ed25519")

    ## Generate and add ssh_config
    ssh_config = api.buildbucket.builder_cache_path.join('ssh_config')
    api.ssh.generate_ssh_config(
        private_key_path=api.path.basename(ssh_files.id_private),
        dest=ssh_config)
    add(ssh_config, "ssh_config")

  def addFlutterTests():
    add(
        checkout.join('out', 'fuchsia_bucket', 'flutter', 'x64', 'debug', 'aot',
                      'flutter_aot_runner-0.far'), 'flutter_aot_runner-0.far')
    test_fars_file = checkout.join('flutter', 'testing', 'fuchsia', 'test_fars')
    test_fars = api.file.read_text('Retrieve list of test FARs',
                                   test_fars_file).split('\n')
    for far in test_fars:
      if (len(far) > 0) and (not far.startswith('#')):
        add(checkout.join('out', 'fuchsia_debug_x64', far), far)
        flutter_tests.append(far)

  def addTestScript():
    test_script = api.resource('run_vdl_test.sh')
    api.step('change file permission', ['chmod', '777', test_script])
    add(test_script, "run_vdl_test.sh")

  addVDLFiles()
  addPackageFiles()
  addImageFiles()
  addTestScript()
  addFlutterTests()

  isolate_tree.create_links("create tree of vdl runfiles")
  isolated = api.isolated.isolated(isolate_tree.root)
  isolated.add_dir(isolate_tree.root)
  hash = isolated.archive('Archive FEMU Run Files')
  return flutter_tests, root_dir, hash


def TestFuchsiaFEMU(api):
  """Run flutter tests on FEMU."""
  test_args = {
      'txt_tests':
          '--gtest_filter=-ParagraphTest.*',
      'fml_tests':
          '--gtest_filter=-MessageLoop.TimeSensistiveTest_*:FileTest.CanTruncateAndWrite:FileTest.CreateDirectoryStructure',
      'shell_tests':
      '--gtest_filter=-ShellTest.ReportTimingsIsCalledLaterInReleaseMode:ShellTest.ReportTimingsIsCalledSoonerInNonReleaseMode',
      'flutter_runner_scenic_tests':
          '--gtest_filter=-SessionConnectionTest.*:CalculateNextLatchPointTest.*',
  }
  flutter_tests, root_dir, isolated_hash = IsolateSymlink(api)
  cmd = ['./run_vdl_test.sh']
  # These flags will be passed through to VDL
  cmd.append('--emulator_binary_path=aemu/emulator')
  cmd.append('--proto_file_path=virtual_device.textproto')
  cmd.append('--pm_tool=pm')
  cmd.append('--far_tool=far')
  cmd.append('--fvm_tool=fvm')
  cmd.append('--resize_fvm=2G')
  cmd.append('--gpu=swiftshader_indirect')
  cmd.append('--headless_mode=true')
  cmd.append('--xvfb=false')
  cmd.append('--enable_grpc_server=false')
  cmd.append('--enable_grpc_tls=false')
  cmd.append(
      '--system_images=' \
      '{build_args},{kernel},{fvm},{zircona},{ssh_config},{ssh_id_public},' \
      '{ssh_id_private},{package_archive}' \
      .format(
          build_args='qemu_buildargs',
          kernel='qemu_kernel',
          fvm='qemu_fvm',
          zircona='qemu_zircona-ed25519',
          ssh_config='ssh_config',
          ssh_id_public='id_ed25519.pub',
          ssh_id_private='id_ed25519',
          package_archive='package_archive',
      ))

  with api.context(cwd=root_dir):
    with api.step.nest('FEMU Test') as presentation:
      for test in flutter_tests:
        package_name = re.search('(?P<package_name>.*)-\d+.far', test)
        if package_name and package_name.group('package_name'):
          pkg = package_name.group('package_name')
          test_cmd = cmd[:]
          test_cmd.append(
              '--serve_packages=flutter_aot_runner-0.far,{test}'.format(
                  test=test))
          test_cmd.append('--run_test={pkg}'.format(pkg=pkg))
          if test_args.has_key(pkg):
            test_cmd.append('--test_args={args}'.format(args=test_args[pkg]))
          try:
            api.step(
                'Run FEMU Test %s' % pkg,
                test_cmd + [
                    '--emulator_log',
                    api.raw_io.output_text(name='emulator_log'),
                    '--syslog',
                    api.raw_io.output_text(name='syslog'),
                ],
                step_test_data=(lambda: api.raw_io.test_api.output_text(
                    'failure', name='syslog')))

          finally:
            step_result = api.step.active_result
            step_result.presentation.logs[
                'syslog'] = step_result.raw_io.output_texts['syslog']
            step_result.presentation.logs[
                'emulator_log'] = step_result.raw_io.output_texts[
                    'emulator_log']


def BuildFuchsia(api):
  """
  Schedules release builds for x64 on other bots, and then builds the x64 runners
  (which do not require LTO and thus are faster to build).

  On Linux, we also run tests for the runner against x64, and if they fail
  we cancel the scheduled builds.
  """

  checkout = GetCheckoutPath(api)
  build_script = str(
      checkout.join('flutter/tools/fuchsia/build_fuchsia_artifacts.py'))
  git_rev = api.buildbucket.gitiles_commit.id or 'HEAD'
  BuildAndTestFuchsia(api, build_script, git_rev)


def RunSteps(api, properties, env_properties):
  cache_root = api.buildbucket.builder_cache_path
  checkout = GetCheckoutPath(api)
  api.file.ensure_directory('Ensure checkout cache', cache_root)
  api.goma.ensure()
  dart_bin = checkout.join('third_party', 'dart', 'tools', 'sdks', 'dart-sdk',
                           'bin')

  env = {'GOMA_DIR': api.goma.goma_dir}
  env_prefixes = {'PATH': [dart_bin]}

  api.repo_util.engine_checkout(
      cache_root, env, env_prefixes, clobber=properties.clobber)

  # Various scripts we run assume access to depot_tools on path for `ninja`.
  with api.context(
      cwd=cache_root, env=env,
      env_prefixes=env_prefixes), api.depot_tools.on_path():
    if api.platform.is_linux and api.properties.get('build_fuchsia', True):
      BuildFuchsia(api)


############ RECIPE TEST ############


def GenTests(api):
  output_props = struct_pb2.Struct()
  output_props['isolated_output_hash'] = 'deadbeef'
  build = api.buildbucket.try_build_message(
      builder='FEMU Test', project='flutter')
  build.output.CopyFrom(build_pb2.Build.Output(properties=output_props))

  yield api.test(
      'start_femu_with_vdl',
      api.properties(
          InputProperties(
              goma_jobs='1024',
              build_fuchsia=True,
              test_fuchsia=True,
              git_url='https://github.com/flutter/engine',
              git_ref='refs/pull/1/head',
              clobber=False,
          ),),
      api.step_data(
          'Retrieve list of test FARs',
          api.file.read_text(
              '#this is a comment\nui_tests-0.far\nfml_tests-0.far\ntest3-x.far'
          ),
      ),
      api.step_data(
          'Read manifest',
          api.file.read_json({'id': '0.20200101.0.1'}),
      ),
      api.properties.environ(EnvProperties(SWARMING_TASK_ID='deadbeef')),
      api.platform('linux', 64),
      api.path.exists(
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_image/linux_intel_64/buildargs.gn'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_image/linux_intel_64/qemu-kernel.kernel'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_image/linux_intel_64/storage-full.blk'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_image/linux_intel_64/zircon-a.zbi'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_packages/linux_intel_64/pm'),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_packages/linux_intel_64/amber-files'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_packages/linux_intel_64/qemu-x64.tar.gz'
          ),
          api.path['cache'].join('builder/ssh/id_ed25519.pub'),
          api.path['cache'].join('builder/ssh/id_ed25519'),
          api.path['cache'].join('builder/ssh/ssh_host_key.pub'),
          api.path['cache'].join('builder/ssh/ssh_host_key'),
      ),
  )

  yield api.test(
      'no_zircon_file',
      api.properties(
          InputProperties(
              goma_jobs='1024',
              build_fuchsia=True,
              test_fuchsia=True,
              git_url='https://github.com/flutter/engine',
              git_ref='refs/pull/1/head',
          ),),
      api.step_data(
          'Read manifest',
          api.file.read_json({'id': '0.20200101.0.1'}),
      ),
      api.platform('linux', 64),
      api.path.exists(
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_image/linux_intel_64/buildargs.gn'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_image/linux_intel_64/qemu-kernel.kernel'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_image/linux_intel_64/storage-full.blk'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_packages/linux_intel_64/pm'),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_packages/linux_intel_64/amber-files'
          ),
          api.path['cache'].join(
              'builder/0.20200101.0.1/fuchsia_packages/linux_intel_64/qemu-x64.tar.gz'
          ),
          api.path['cache'].join('builder/ssh/id_ed25519.pub'),
          api.path['cache'].join('builder/ssh/id_ed25519'),
          api.path['cache'].join('builder/ssh/ssh_host_key.pub'),
          api.path['cache'].join('builder/ssh/ssh_host_key'),
      ),
  )
