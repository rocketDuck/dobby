#!/usr/bin/env bash
set -e
mkdir -p bin dist repo
rm -f bin/* dist/* repo/*
poetry build
poetry export --without-hashes --format=requirements.txt --output=requirements.txt
pip wheel --wheel-dir=repo --constraint=requirements.txt PyYAML
# Hack, but PyYAML in that configuration is actually a universal wheel
mv repo/PyYAML-5.3.1-cp38-cp38-linux_x86_64.whl repo/PyYAML-5.3.1-py3-none-any.whl
pex dist/dobby-*.whl --output-file=bin/dobby --script=dobby --disable-cache --no-compile --no-build --no-use-system-time \
    --constraints=requirements.txt --python-shebang='/usr/bin/env python3' \
    --find-links=file://`pwd`/repo \
    --python=python3.7 --python=python3.8 \
    --platform=manylinux1-x86_64-cp-37-m --platform=manylinux1-x86_64-cp-38-cp38 \
    --platform=win-amd64-cp-37-m --platform=win-amd64-cp-38-cp38 \
    --platform=macosx-10.6-intel-cp-37-m --platform=macosx-10.9-x86_64-cp-38-cp38
