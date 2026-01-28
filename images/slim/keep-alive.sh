#! /usr/bin/env bash

if [[ -n $1 ]]; then
    hours=$1
else
    echo -n "Enter number of hours to keep notebook alive: "
    read hours
fi

if ! [[ $hours =~ ^[0-9]+$ ]]; then
    echo "Hours must be an integer."
    exit 1
fi

if [[ $hours -lt 0 ]]; then
    echo "Hours cannot be negative."
    exit 1
fi

notebook="$(basename "${NB_PREFIX}")"
namespace="${NB_NAMESPACE}"

timestamp="$(date +"%Y-%m-%dT%H:%M:%SZ" -d "+"${hours}" hour")"

set -e

kubectl annotate notebook "${notebook}" -n "${namespace}" notebooks.kubeflow.org/last_activity_check_timestamp="${timestamp}" --overwrite
kubectl annotate notebook "${notebook}" -n "${namespace}" notebooks.kubeflow.org/last-activity="${timestamp}" --overwrite

echo "Script completed successfully"
