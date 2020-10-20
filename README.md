# Flutter LUCI Recipes

This repository contains Flutter's LUCI recipes. For the LUCI infrastructure
config, see [flutter/infra on GitHub](https://github.com/flutter/infra). Actual
builds can be seen at [ci.chromium.org](https://ci.chromium.org/p/flutter).

## Config

[Tricium](https://chromium.googlesource.com/infra/infra/+/master/go/src/infra/tricium/README.md) configurations recipes repo.

## Recipe Branching for Releases

The script `branch_recipes.py` is used to generate new copies of the LUCI
recipes for a beta release. See [Recipe Branching for Releases](https://github.com/flutter/flutter/wiki/Recipe-Branching-for-Releases)
for more information. For usage:

```
$ ./branch_recipes.py --help
```
