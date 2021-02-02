#!/usr/bin/env python

import getopt
import os
import re
import shutil
import subprocess
import sys

# A path relative to DESIRED_CWD, omitting file extension (assumed to be '.py')
RECIPES_TO_BRANCH = (
        'devicelab',
        'devicelab/devicelab_drone',
        'engine/engine_arm',
        'engine/engine_metrics',
        'engine/scenarios',
        'engine/web_engine_framework',
        'engine/web_engine_drone',
        'engine',
        'engine_builder',
        'femu_test',
        'flutter/flutter',
        'flutter/flutter_drone',
        'flutter',
        'web_engine',
        )

# These recipes are not used in a Flutter release build, and thus do not need to
# be branched.
RECIPES_TO_SKIP = (
        'cocoon/cocoon',
        'cocoon/device_doctor',
        'firebaselab/firebaselab',
        'fuchsia/fuchsia',
        'fuchsia_ctl',
        'ios-usb-dependencies',
        'plugins/plugins',
        'recipes',
        'tricium/tricium',
        )

repo_root = os.path.dirname(os.path.realpath(__file__))
RECIPES_DIR = os.path.join(repo_root, 'recipes')

def usage(optional_options, required_options, exit_code=0):
    """Print script usage and exit."""
    print('A command-line tool for generating legacy recipes for release ' +
            'branches.\n')
    print('Usage: ./branch_recipes.py --flutter-version=<flutter version string> ' +
            '--recipe-revision=<recipes git hash>\n')
    print('Where --flutter-version is of the form x_y_0 and represents the ' +
            'stable release\nthe branch in question is a candidate for, and '
            '--recipe-revision is the recipes\nrepo revision at the time the '
            'release branch was branched off of master.\n')
    print('Required options:')
    for opt in required_options:
        print('  --' + opt)
    print('\nOptional options:')
    for opt in optional_options:
        print('  --' + opt)
    sys.exit(exit_code)

def parse_arguments(argv):
    """Parse and validate command line arguments."""
    options = {
            'force': False,
            'delete': False,
            }
    try:
        optional_options = ('force', 'help', 'delete')
        required_options = ('flutter-version=', 'recipe-revision=')
        opts, _args = getopt.getopt(argv, '', optional_options + required_options)
    except getopt.GetoptError:
        print('Error parsing arguments!\n')
        usage(optional_options, required_options, 1)
    for opt, arg in opts:
        if opt == '--help':
            usage(optional_options, required_options, 0)
        elif opt == '--force':
            options['force'] = True
        elif opt == '--flutter-version':
            if not re.search(r'^\d+_\d+_0+$', arg):
                print('Error! Invalid value passed to --flutter-version: "%s"' %
                        arg)
                print('It should be of the form x_y_0')
                sys.exit(1)
            options['flutter-version='] = arg
        elif opt == '--recipe-revision':
            if not re.search(r'^[0-9a-z]{40}$', arg):
                print('Error! Invalid value passed to --recipe-revision: "%s"' %
                        arg)
                print('It should be a valid git hash')
                sys.exit(1)
            options['recipe-revision='] = arg
        elif opt == '--delete':
            options['delete'] = True
    # validate
    if options['delete']:
        if 'flutter-version=' not in options:
            print('meep')
            print(options)
            usage(optional_options, required_options, 1)
    else:
        if 'flutter-version=' not in options or 'recipe-revision=' not in options:
            print('moop')
            print(options)
            usage(optional_options, required_options, 1)
    return options

def get_recipes(working_directory):
    """Returns the paths to recipes and expectation file directories.

    Args:
        working_directory (str): absolute path to the directory where the recipes
            are located.

    Returns:
        latest_recipes (str[]): paths to all unbranched recipes.
        branched_recipes (str[]): paths to all branched recipes.
        branched_expectations (str[]): paths to all expectation directories of
            branches recipes.
    """
    recipe_pattern = r'\.py$'
    branched_recipe_pattern = r'_\d+_\d+_\d+\.py$'
    expectation_pattern = r'\.expected$'
    latest_recipes = []
    branched_recipes = []
    branched_expectations = []
    for root, dirs, files in os.walk(working_directory):
        for filename in files:
            if (re.search(recipe_pattern, filename)):
                if re.search(branched_recipe_pattern, filename):
                    branched_recipes.append(os.path.join(root, filename))
                else:
                    latest_recipes.append(os.path.join(root, filename))
        for dir_name in dirs:
            if re.search(expectation_pattern, dir_name):
                branched_expectations.append(os.path.join(root, dir_name))
    return latest_recipes, branched_recipes, branched_expectations

def contains(file_path, prefix, tuple_of_candidates):
    """Given the full path to a file, returns the recipe sub-string.

    If in the supplied tuple of candidates

    Args:
        file_path (str): Path to the file to look up.
        prefix (str): Absolute path to directory containing all recipes.
        tuple_of_candidates (str()): Tuple containing expected sub-strings.
            Return None if file_path does not map to one of these.

    Returns (str | None): recipe sub-string if the file is contained in the
        provided candidates, else None.
    """
    for candidate in tuple_of_candidates:
        if file_path == os.path.join(prefix, candidate + r'.py'):
            return candidate
    return None

def branch_recipes(options):
    """Branch all latest recipes on disk."""
    latest_recipes, _branched_recipes, _branched_expectations = get_recipes(RECIPES_DIR)
    for recipe in latest_recipes:
        recipe_sub_string = contains(recipe, RECIPES_DIR, RECIPES_TO_BRANCH)
        if recipe_sub_string is not None:
            print('Reading file %s from revision %s' % (recipe,
                options['recipe-revision=']))
            # git show <revision>:path/to/recipe
            code = subprocess.check_output(
                    [
                        'git',
                        'show',
                        '%s:./%s' % (options['recipe-revision='], recipe_sub_string + r'.py'),
                        ],
                    cwd=RECIPES_DIR,
                    ).decode('utf-8')
            new_file_path = '%s/%s_%s.py' % (RECIPES_DIR, recipe_sub_string,
                    options['flutter-version='])
            if os.path.exists(new_file_path):
                if options['force']:
                    print('Warning! File %s already exists. About to overwrite...' %
                            new_file_path)
                else:
                    print('Error! File %s already exists. To overwrite, use the --force flag'
                            % new_file_path)
                    sys.exit(1)
            with open(new_file_path, 'w') as new_file:
                print('Writing %s\n' % new_file_path)
                new_file.write(code)
        else:
            assert contains(recipe, RECIPES_DIR, RECIPES_TO_SKIP), 'Expected %s to be branched or skipped.' % recipe

def delete_recipes(options):
    """Delete branched recipes and expectation directories of a given version."""
    _latest_recipes, branched_recipes, branched_expectations = get_recipes(RECIPES_DIR)
    branched_recipes.sort()
    for recipe in branched_recipes:
        suffix = options['flutter-version='] + r'.py'
        if recipe.endswith(suffix):
            print('Deleting file %s' % recipe)
            os.remove(recipe)
    for expectations in branched_expectations:
        suffix = options['flutter-version='] + r'.expected'
        if expectations.endswith(suffix):
            print('Deleting directory %s' % expectations)
            shutil.rmtree(expectations)


def main(argv):
    options = parse_arguments(sys.argv[1:])

    if options['delete']:
        delete_recipes(options)
    else:
        branch_recipes(options)

main(sys.argv[1:])
