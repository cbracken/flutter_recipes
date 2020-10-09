#!/bin/bash

# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Validates gallery builds for both linux and darwin platforms.

set -e
./dev/bots/deploy_gallery.sh
