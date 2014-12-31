#!/bin/bash

if [[ ${TRAVIS_PULL_REQUEST} == "false" ]] && [[ ${TRAVIS_BRANCH} == "master" ]]; then

    echo "uploading docs"

    REV=`git rev-parse HEAD`

    # Build the docs
    tox -e apidocs

    # Make the directory
    git clone --branch gh-pages https://github.com/twisted/tubes.git /tmp/tmp-docs

    # Copy the docs
    rsync -rt --del --exclude=".git" apidocs/* /tmp/tmp-docs/docs/

    cd /tmp/tmp-docs

    # set the username and email
    git config user.name "${GIT_USER}"
    git config user.email "${GIT_EMAIL}"

    git add -A
    git commit -m "Built from ${REV}"

    # Push it up
    git push -q "https://${GH_TOKEN}@github.com/twisted/tubes.git"
else
    echo "skipping docs upload"
fi;
