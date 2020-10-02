#!/usr/bin/env bash
# TODO: Set a high ulimit for large shuffles
# Need to find a way to do this, since "sudo ulimit..." doesn't fly.
# Probably need to edit some Linux config file.
ulimit -n 65536
ulimit -u 65536
