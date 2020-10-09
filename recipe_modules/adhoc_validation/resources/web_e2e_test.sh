#!/bin/bash

# Web integration tests using integration_test (aka e2e) package.

set -e

flutter config --enable-web
chromedriver --port=4444 &
sleep 5
cd dev/integration_tests/web_e2e_tests/
flutter drive --target=test_driver/text_editing_integration.dart -d web-server --browser-name=chrome
pkill chromedriver
