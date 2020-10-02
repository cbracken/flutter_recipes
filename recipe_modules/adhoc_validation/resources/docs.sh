#!/bin/bash

# Copyright 2020 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

export FIREBASE_MASTER_TOKEN=`cat $FIREBASE_MASTER_TOKEN`
export FIREBASE_PUBLIC_TOKEN=`cat $FIREBASE_PUBLIC_TOKEN`
./dev/bots/docs.sh
