#!/bin/bash

# Run a test application in the phone to dismiss ios dialogs.
# This script expects the phone id as a parameter: dismiss_dialogs.sh <ios id>.
set -e

# This is only needed for devicelab machines and unlock_login_keychain is only
# provisioned on devicelab machines.
if [ -f /usr/local/bin/unlock_login_keychain.sh ]
then
  /usr/local/bin/unlock_login_keychain.sh
  xcrun xcodebuild -project infra-dialog.xcodeproj -scheme infra-dialog -destination id=$1 test CODE_SIGN_STYLE=Manual DEVELOPMENT_TEAM=S8QB4VV633 PROVISIONING_PROFILE_SPECIFIER='match Development *'
fi
