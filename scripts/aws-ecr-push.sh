#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  scripts/aws-ecr-push.sh --repo-uri <account>.dkr.ecr.<region>.amazonaws.com/<repo> --tag <tag> [--profile <profile>] [--dockerfile <path>] [--context <dir>] [--create-repo]

Examples:
  scripts/aws-ecr-push.sh --repo-uri 469510588503.dkr.ecr.eu-west-2.amazonaws.com/floodwatch-api --tag main --profile iamadmin-general --create-repo
  scripts/aws-ecr-push.sh --repo-uri 469510588503.dkr.ecr.eu-west-2.amazonaws.com/floodwatch-worker --tag main --profile iamadmin-general --dockerfile Dockerfile --context .

Outputs:
  Prints the full image identifier to use in CloudFormation (repo-uri:tag).
USAGE
}

profile=""
repo_uri=""
tag=""
dockerfile="Dockerfile"
context="."
create_repo="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)
      profile="${2:-}"; shift 2
      ;;
    --repo-uri)
      repo_uri="${2:-}"; shift 2
      ;;
    --tag)
      tag="${2:-}"; shift 2
      ;;
    --dockerfile)
      dockerfile="${2:-}"; shift 2
      ;;
    --context)
      context="${2:-}"; shift 2
      ;;
    --create-repo)
      create_repo="true"; shift 1
      ;;
    -h|--help)
      usage; exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$repo_uri" || -z "$tag" ]]; then
  usage
  exit 2
fi

if [[ ! -f "$dockerfile" ]]; then
  echo "Dockerfile not found: $dockerfile" >&2
  exit 2
fi

if [[ ! -d "$context" ]]; then
  echo "Context dir not found: $context" >&2
  exit 2
fi

repo_name="${repo_uri##*/}"
registry_host="${repo_uri%%/*}"

if [[ "$registry_host" != *.dkr.ecr.*.amazonaws.com ]]; then
  echo "Invalid ECR repo host: $registry_host" >&2
  echo "Expected: <account>.dkr.ecr.<region>.amazonaws.com" >&2
  exit 2
fi

region="$(echo "$registry_host" | sed -E 's/^([0-9]+)\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com$/\2/')"
account_id="$(echo "$registry_host" | sed -E 's/^([0-9]+)\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com$/\1/')"

aws_args=(--region "$region")
if [[ -n "$profile" ]]; then
  aws_args+=(--profile "$profile")
fi

if [[ "$create_repo" == "true" ]]; then
  aws ecr describe-repositories "${aws_args[@]}" --repository-names "$repo_name" >/dev/null 2>&1 || \
    aws ecr create-repository "${aws_args[@]}" --repository-name "$repo_name" >/dev/null
fi

aws ecr get-login-password "${aws_args[@]}" | docker login --username AWS --password-stdin "$account_id.dkr.ecr.$region.amazonaws.com" >/dev/null

image_local="floodwatch-ecr-push:${tag}"
docker build -t "$image_local" -f "$dockerfile" "$context" >/dev/null

image_remote="${repo_uri}:${tag}"
docker tag "$image_local" "$image_remote"
docker push "$image_remote"

echo "$image_remote"
