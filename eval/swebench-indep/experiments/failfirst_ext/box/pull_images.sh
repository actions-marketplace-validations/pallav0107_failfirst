#!/bin/bash
# Resumable, paced, sequential pull of the sampled instance images (public Docker Hub, anonymous).
#   nohup setsid bash pull_images.sh images.txt LOGDIR > /dev/null 2>&1 &
# Skips images already present, so re-running resumes. Throttling ("toomanyrequests") is
# logged and waited out without counting as a failed try. Every outcome lands in
# LOGDIR/pull_status.tsv (image, ok|missing|failed, seconds); a timeline in LOGDIR/pull.log.
set -u
LIST=${1:?usage: pull_images.sh images.txt [logdir]}
DIR=${2:-.}
LOG="$DIR/pull.log"; STATUS="$DIR/pull_status.tsv"
PACE=${PACE_S:-30}          # pause between pulls
BACKOFF=${BACKOFF_S:-1200}  # wait after a throttle response
MAX_TRIES=${MAX_TRIES:-6}   # non-throttle failures per image
log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }
echo $$ > "$DIR/pull.pid"
log "start pid $$ list $LIST"
while read -r img; do
  case "$img" in ''|\#*) continue ;; esac
  if docker image inspect "$img" > /dev/null 2>&1; then log "present $img"; continue; fi
  tries=0
  while :; do
    t0=$(date +%s)
    out=$(docker pull -q "$img" 2>&1); rc=$?
    dt=$(( $(date +%s) - t0 ))
    if [ $rc -eq 0 ]; then
      log "pulled $img ${dt}s"; printf '%s\tok\t%s\n' "$img" "$dt" >> "$STATUS"; break
    fi
    if echo "$out" | grep -qi -E 'toomanyrequests|rate limit'; then
      log "THROTTLED $img: waiting ${BACKOFF}s ($(echo "$out" | tail -c 200 | tr '\n' ' '))"
      sleep "$BACKOFF"; continue
    fi
    if echo "$out" | grep -qi -E 'manifest unknown|not found|does not exist|repository does not exist'; then
      log "MISSING $img: $(echo "$out" | tail -c 200 | tr '\n' ' ')"
      printf '%s\tmissing\t%s\n' "$img" "$dt" >> "$STATUS"; break
    fi
    tries=$((tries + 1))
    log "error $img try $tries rc $rc: $(echo "$out" | tail -c 200 | tr '\n' ' ')"
    if [ $tries -ge "$MAX_TRIES" ]; then
      log "GAVE UP $img"; printf '%s\tfailed\t%s\n' "$img" "$dt" >> "$STATUS"; break
    fi
    sleep 60
  done
  sleep "$PACE"
done < "$LIST"
log "done"
rm -f "$DIR/pull.pid"
