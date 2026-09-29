#!/bin/sh
set -eu
umask 077

if [ -n "${EASEL_RAW_STREAM_PATH:-}" ]; then
    stream_path="$EASEL_RAW_STREAM_PATH"
else
    stream_dir="$HOME/.openclaw-easel"
    mkdir -p "$stream_dir"
    chmod 700 "$stream_dir"
    stream_path="$stream_dir/easel-raw-stream.jsonl"
fi

mkdir -p "$(dirname "$stream_path")"
[ ! -L "$stream_path" ] || { echo "Refusing symlink raw-stream path" >&2; exit 1; }
: > "$stream_path"
chmod 600 "$stream_path"

export EASEL_RAW_STREAM_PATH="$stream_path"
export OPENCLAW_RAW_STREAM=1
export OPENCLAW_RAW_STREAM_PATH="$stream_path"
if [ -n "${NODE_OPTIONS:-}" ]; then
    export NODE_OPTIONS="$NODE_OPTIONS --max-old-space-size=8192"
else
    export NODE_OPTIONS="--max-old-space-size=8192"
fi

openclaw_bin="$(command -v openclaw || true)"
[ -n "$openclaw_bin" ] || { echo "OpenClaw executable not found in service PATH" >&2; exit 1; }
exec "$openclaw_bin" "$@"
