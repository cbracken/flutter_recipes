from recipe_engine.recipe_api import Property
from recipe_engine.config import ConfigGroup, Single

DEPS = [
    'depot_tools/osx_sdk',
    'recipe_engine/cipd',
    'recipe_engine/context',
    'recipe_engine/file',
    'recipe_engine/path',
    'recipe_engine/platform',
    'recipe_engine/step',
    ]

PROPERTIES = {
  '$flutter/flutter_osx_sdk': Property(
    help='Properties specifically for the flutter osx_sdk module.',
    param_name='sdk_properties',
    kind=ConfigGroup(  # pylint: disable=line-too-long
      iphoneos_sdk=Single(str),
      iphonesimulator_sdk=Single(str),
      ld=Single(str),
    ), default={},
  )
}
