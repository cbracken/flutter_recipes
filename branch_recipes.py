#!/usr/bin/env python

import getopt
import os
import re
import subprocess
import sys

# A path relative to DESIRED_CWD, omitting file extension (assumed to be '.py')
RECIPES_TO_BRANCH = (
        'devicelab',
        'devicelab/devicelab_drone',
        'engine/scenarios',
        'engine/web_engine_framework',
        'engine',
        'engine_builder',
        'femu_test',
        'flutter/flutter',
        'flutter/flutter_drone',
        'flutter',
        'web_engine',
        )
RECIPES_TO_SKIP = (
        'cocoon',
        'firebaselab/firebaselab',
        'fuchsia/fuchsia',
        'fuchsia_ctl',
        'ios-usb-dependencies',
        'plugins/plugins',
        'recipes',
        'tricium/tricium',
        )

repo_root = os.path.dirname(os.path.realpath(__file__))
recipes_dir = os.path.join(repo_root, 'recipes')

def usage(optional_options, required_options):
    print('A command-line tool for generating legacy recipes for release ' +
            'branches.\n')
    print('Usage: ./branch_recipes.py --flutter-version=<flutter version string> ' +
            '--recipe-revision=<recipes git hash>\n')
    print('Where --flutter-version is of the form x_y_z and represents the ' +
            'stable release\nthe branch in question is a candidate for, and '
            '--recipe-revision is the recipes\nrepo revision at the time the '
            'release branch was branched off of master.\n')
    print('Required options:')
    for opt in required_options:
        print('  --' + opt)
    print('\nOptional options:')
    for opt in optional_options:
        print('  --' + opt)

def parse_arguments(argv):
    options = {
            'force': False,
            }
    try:
        optional_options = ('force', 'help')
        required_options = ('flutter-version=', 'recipe-revision=')
        opts, args = getopt.getopt(argv, '', optional_options + required_options)
    except getopt.GetoptError:
        usage(optional_options, required_options)
        sys.exit(1)
    for opt, arg in opts:
        if opt == '--help':
            usage(optional_options, required_options)
            sys.exit(0)
        elif opt == '--force':
            options['force'] = True
        elif opt == '--flutter-version':
            if not re.search(r'^\d+_\d+_\d+$', arg):
                print('Error! Invalid value passed to --flutter-version: "%s"' %
                        arg)
                print('It should be of the form x_y_z')
                sys.exit(1)
            options['flutter-version='] = arg
        elif opt == '--recipe-revision':
            if not re.search(r'^[0-9a-z]{40}$', arg):
                print('Error! Invalid value passed to --flutter-version: "%s"' %
                        arg)
                print('It should be a valid git hash')
                sys.exit(1)
            options['recipe-revision='] = arg
    for required_opt in required_options:
        if options.get(required_opt, None) is None:
            usage(optional_options, required_options)
            sys.exit(1)
    return options

def get_all_recipes(cwd):
    recipe_pattern = r'\.py$'
    forked_recipe_pattern = r'_\d+_\d+_\d+\.py$'
    expectation_pattern = r'\.expected$'
    accumulated_files = []
    for root, dirs, files in os.walk(cwd):
        for filename in files:
            if (re.search(recipe_pattern, filename) and not
                re.search(forked_recipe_pattern, filename)):
                accumulated_files.append(os.path.join(root, filename))
        for dir in dirs:
            if not re.search(expectation_pattern, dir):
                accumulated_files += get_all_recipes(os.path.join(root, dir))
    return accumulated_files

def contains(subject, prefix, tuple_of_candidates):
    for candidate in tuple_of_candidates:
        if subject == os.path.join(prefix, candidate + r'.py'):
            return candidate
    return None

def main(argv):
    options = parse_arguments(sys.argv[1:])

    recipes = get_all_recipes(recipes_dir)
    for recipe in recipes:
        recipe_sub_string = contains(recipe, recipes_dir, RECIPES_TO_BRANCH)
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
                    cwd=recipes_dir,
                    ).decode('utf-8')
            new_file_path = '%s/%s_%s.py' % (recipes_dir, recipe_sub_string,
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
            assert contains(recipe, recipes_dir, RECIPES_TO_SKIP), 'Expected %s to be branched or skipped.' % recipe

main(sys.argv[1:])
