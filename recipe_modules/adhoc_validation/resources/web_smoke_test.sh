#!/bin/bash

# Web smoke tests.

set -e

flutter config --enable-web
chromedriver --port=4444 &
sleep 5
cd examples/hello_world/
flutter drive --target=test_driver/smoke_web_engine.dart -d web-server --profile --browser-name=chrome
pkill chromedriver
