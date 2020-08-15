REM Copyright 2020 The Chromium Authors. All rights reserved.
REM Use of this source code is governed by a BSD-style license that can be
REM found in the LICENSE file.

CMD /S /C "IF EXIST "bin\cache\pkg\tests\" RMDIR /S /Q bin\cache\pkg\tests"
git clone https://github.com/flutter/tests.git bin\cache\pkg\tests
dart --enable-asserts dev\customer_testing\run_tests.dart --skip-on-fetch-failure --skip-template bin/cache/pkg/tests/registry/*.test
