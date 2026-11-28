#!/usr/bin/env sh
# Print the runtime versions the Dockerfiles ship, as GitHub step outputs.
#
# CI and the security scans test with exactly what production runs. When
# Dependabot bumps a base image in a Dockerfile, CI follows without a second
# edit, so the two can no longer drift apart (CI once tested Node 24 and
# nginx 1.27 while the images shipped Node 26 and nginx 1.31).
#
# Usage (from the repository root): sh .github/scripts/runtime-versions.sh
set -eu

read_from() {
  # $1 = sed expression capturing the wanted part, $2 = Dockerfile
  value=$(sed -nE "$1" "$2" | head -n 1)
  if [ -z "$value" ]; then
    echo "::error file=$2::could not read the base image version" >&2
    exit 1
  fi
  printf '%s' "$value"
}

python=$(read_from 's/^FROM python:([0-9]+\.[0-9]+)[-.].*/\1/p' backend/Dockerfile)
crm_node=$(read_from 's/^FROM node:([0-9]+)[-.].*/\1/p' crm/Dockerfile)
landing_node=$(read_from 's/^FROM node:([0-9]+)[-.].*/\1/p' landing/Dockerfile)
landing_nginx=$(read_from 's/^FROM (nginx:[^ ]+).*/\1/p' landing/Dockerfile)

{
  echo "python=$python"
  echo "crm_node=$crm_node"
  echo "landing_node=$landing_node"
  echo "landing_nginx=$landing_nginx"
} | tee -a "${GITHUB_OUTPUT:-/dev/null}"
