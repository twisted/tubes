#!/bin/bash

if [[ "TRAVIS_PULL_REQUEST" == "false" ]] && [[ "TRAVIS_BRANCH" == "master" ]]; then

    echo "uploading docs"

    pip install pydoctor

    REV=`git rev-parse HEAD`

    git clone --branch gh-pages https://github.com/twisted/tubes.git /tmp/tmp-docs

    pydoctor tubes

    rsync -rt --del --exclude=".git" apidocs /tmp/tmp-docs/docs/

    cd /tmp/tmp-docs

    git config user.name "${GIT_USER}"
    git config user.email "${GIT_EMAIL}"

    git add -A
    git commit -m "Built from ${REV}"

    git push -q "https://${GH_TOKEN}@github.com/twisted/tubes.git"
else;
    echo "skipping docs upload"
fi;
