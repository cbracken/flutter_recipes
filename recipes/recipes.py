# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Recipe for testing recipes."""

from recipe_engine.recipe_api import Property
DEPS = [
    'fuchsia/git',
    'fuchsia/commit_queue',
    'fuchsia/recipe_testing',
    'fuchsia/status_check',
    'recipe_engine/buildbucket',
    'recipe_engine/context',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/python',
    'recipe_engine/step',
]
PROPERTIES = {
    'remote':
        Property(
            kind=str,
            help='Remote repository',
            default='https://flutter.googlesource.com/recipes',
        ),
    # Default of True until recipe testing actually works on Flutter.
    'unittest_only':
        Property(kind=bool, help='Finish after unit tests', default=True),
}
# If this build is being triggered from a change to this recipe, we need
# to explicitly pass a CL. The most recent passing run of
# flutter.try/recipes could have any number of different subbuilds kicked
# off. In that case alter the recipes build to run on a specific CL that
# modifies the envtest recipe alone, because that recipe is used by
# relatively few CQ builders.
SELFTEST_CL = ('https://flutter-review.googlesource.com/c/recipes/+/3606')
COMMIT_QUEUE_CFG = """
    submit_options: <
      max_burst: 4
      burst_delay: <
        seconds: 480
      >
    >
    config_groups: <
      gerrit: <
        url: "https://flutter-review.googlesource.com"
        projects: <
          name: "project"
          ref_regexp: "refs/heads/.+"
        >
      >
      verifiers: <
        gerrit_cq_ability: <
          committer_list: "project-flutter-committers"
          dry_run_access_list: "project-flutter-tryjob-access"
        >
        tryjob: <
          builders: <
            name: "flutter/try/flutter-baz"
            location_regexp: ".*"
            location_regexp_exclude: ".+/[+]/.*\\.md"
          >
        >
      >
    >
    config_groups: <
      gerrit: <
        url: "https://flutter-review.googlesource.com"
        projects: <
          name: "flutter/flutter"
          ref_regexp: "refs/heads/.+"
        >
      >
      verifiers: <
        gerrit_cq_ability: <
          committer_list: "project-flutter-committers"
          dry_run_access_list: "project-flutter-tryjob-access"
        >
        tryjob: <
          builders: <
            name: "flutter/try/flutter-bar"
            location_regexp: ".*"
            location_regexp_exclude: ".+/[+]/.*\\.md"
            location_regexp_exclude: ".+/[+].*/docs/.+"
          >
          builders: <
            name: "flutter/try/flutter-foo"
            location_regexp: ".*"
            location_regexp_exclude: ".+/[+]/.*\\.md"
            location_regexp_exclude: ".+/[+].*/docs/.+"
          >
        >
      >
    >
"""


def RunSteps(api, remote, unittest_only):
  checkout_path = api.path['start_dir'].join('recipes')
  bb_input = api.buildbucket.build.input
  if bb_input.gerrit_changes:
    api.git.checkout_cl(bb_input.gerrit_changes[0], checkout_path)
  else:
    api.git.checkout(remote)
  api.recipe_testing.project = 'flutter'
  with api.step.defer_results():
    api.recipe_testing.run_lint(checkout_path)
    api.recipe_testing.run_unit_tests(checkout_path)
  if not unittest_only:
    api.recipe_testing.run_led_tests(checkout_path, SELFTEST_CL)


def GenTests(api):
  yield (api.status_check.test('ci') + api.properties(unittest_only=False) +
         api.commit_queue.test_data(COMMIT_QUEUE_CFG) +
         api.recipe_testing.affected_recipes_data(['none']) +
         api.recipe_testing.build_data(
             'flutter/try/flutter-foo', 'flutter', skip=True) +
         api.recipe_testing.build_data(
             'flutter/try/flutter-bar', 'flutter', skip=True) +
         api.recipe_testing.build_data(
             'flutter/try/flutter-baz', 'project', skip=True))
  yield (api.status_check.test('cq_try') + api.properties(unittest_only=False) +
         api.commit_queue.test_data(COMMIT_QUEUE_CFG) +
         api.recipe_testing.affected_recipes_data(['none']) +
         api.recipe_testing.build_data(
             'flutter/try/flutter-foo', 'flutter', skip=True) +
         api.recipe_testing.build_data(
             'flutter/try/flutter-bar', 'flutter', skip=True) +
         api.recipe_testing.build_data(
             'flutter/try/flutter-baz', 'project', skip=True) +
         api.buildbucket.try_build(
             git_repo='https://flutter.googlesource.com/recipes'))
