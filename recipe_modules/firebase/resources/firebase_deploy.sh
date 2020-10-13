#!/bin/bash

# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

export FIREBASE_TOKEN=`cat $TOKEN_PATH`
firebase --debug deploy --token "$FIREBASE_TOKEN" --project "$GCP_PROJECT" --only hosting
