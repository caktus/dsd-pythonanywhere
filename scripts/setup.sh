#!/bin/bash

if [ -z "$1" ]; then
	echo "Usage: $0 <github-repo-url>"
	exit 1
fi

git clone "$1"
