#!/bin/zsh
# What can the mail window's account do in the real bucket, and what can it not?
#
# Run once after the account and the two managed folders exist (mail_window/README.md, step 1) and
# before the service is given the key. It asks the bucket as that account, by impersonation: no
# key is made here. For that it lends the caller roles/iam.serviceAccountTokenCreator on the
# account and takes it back at the end, whatever happened in between.
#
# It reads no letter: every GET discards the body and keeps the status code. It writes one object,
# mail-audit/setup-check/<utc>-access-check.json, which is the first entry of the window's record.
#
# Expected: every line ends in "ok". Anything else means the narrowing is not what the README says.
set -u
G=~/google-cloud-sdk/bin/gcloud; P=korean-stock-analyzer; B=lxm-drop
SA=lxm-mail-window@$P.iam.gserviceaccount.com
ME=$($G config get-value account 2>/dev/null)
API=https://storage.googleapis.com/storage/v1/b/$B
UP=https://storage.googleapis.com/upload/storage/v1/b/$B/o
bad=0

$G iam service-accounts add-iam-policy-binding "$SA" --project $P --member "user:$ME" \
   --role roles/iam.serviceAccountTokenCreator --quiet >/dev/null || { echo "could not lend the token role"; exit 2; }
give_back() {
  # The policy keeps the member as the account spells it (capitals and all); `gcloud config` gives it
  # in lower case, and a remove that names it differently finds nothing. So ask the policy for the name.
  local m
  m=$($G iam service-accounts get-iam-policy "$SA" --project $P --flatten="bindings[].members" \
        --filter="bindings.role:roles/iam.serviceAccountTokenCreator" --format="value(bindings.members)" 2>/dev/null \
      | grep -i -x "user:$ME" | head -1)
  [ -z "$m" ] && { echo "token role: none of ours on the account"; return; }
  $G iam service-accounts remove-iam-policy-binding "$SA" --project $P --member "$m" \
     --role roles/iam.serviceAccountTokenCreator --quiet >/dev/null 2>&1 \
    && echo "token role taken back" || echo "TOKEN ROLE NOT TAKEN BACK: remove it by hand"
}
trap give_back EXIT

TOKEN=""
for i in $(seq 1 18); do                      # a new binding takes about a minute to be believed
  TOKEN=$($G auth print-access-token --impersonate-service-account "$SA" 2>/dev/null)
  [ -n "$TOKEN" ] && break
  sleep 10
done
[ -z "$TOKEN" ] && { echo "no token after 3 minutes"; exit 2; }
echo "asking as $SA (token not printed)"

want() { # label, expected status, got status
  if [ "$2" = "$3" ]; then printf '%-58s HTTP %s  ok\n' "$1" "$3"; else printf '%-58s HTTP %s  EXPECTED %s\n' "$1" "$3" "$2"; bad=1; fi
}
code() { curl -sS -m 30 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$@"; }
enc() { python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$1"; }

# the letters: list and read inside the folder, nothing outside it
want "list drop-root/hub-ops/from-lxm/"            200 "$(code "$API/o?prefix=drop-root/hub-ops/from-lxm/&fields=items(name,size),nextPageToken&maxResults=5")"
want "get  drop-root/hub-ops/from-lxm/001-envelope.json" 200 "$(code "$API/o/$(enc drop-root/hub-ops/from-lxm/001-envelope.json)?alt=media")"
for p in "" "drop-root/" "drop-root/hub-ops" "drop-root/letters/" "drop-root/bbs-plaza/" "drop-state/" "drop-audit/" "mail-audit/"; do
  want "list prefix='$p'"                           403 "$(code "$API/o?prefix=$p&maxResults=5")"
done
for o in drop-root/letters/from-ludex/001-envelope.json drop-state/jdot-hq/00000001.state drop-audit/line; do
  want "get  $o"                                    403 "$(code "$API/o/$(enc $o)?alt=media")"
done
want "write into drop-root/hub-ops/"                403 "$(code -X POST -H 'Content-Type: text/plain' --data x "$UP?uploadType=media&name=$(enc drop-root/hub-ops/from-lxm/access-check.txt)")"
want "delete a letter"                              403 "$(code -X DELETE "$API/o/$(enc drop-root/hub-ops/from-lxm/001-envelope.json)")"

# the record: create, and nothing else
NAME="mail-audit/setup-check/$(date -u +%Y%m%dT%H%M%SZ)-access-check.json"
BODY="{\"kind\":\"setup-check\",\"at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"by\":\"scripts/mail_window_access_check.sh\"}"
want "create $NAME"                                 200 "$(code -X POST -H 'Content-Type: application/json' --data "$BODY" "$UP?uploadType=media&ifGenerationMatch=0&name=$(enc $NAME)")"
want "create it again, never replace"               412 "$(code -X POST -H 'Content-Type: application/json' --data "$BODY" "$UP?uploadType=media&ifGenerationMatch=0&name=$(enc $NAME)")"
want "replace it without the condition"             403 "$(code -X POST -H 'Content-Type: application/json' --data "$BODY" "$UP?uploadType=media&name=$(enc $NAME)")"
want "read it back"                                 403 "$(code "$API/o/$(enc $NAME)?alt=media")"
want "delete it"                                    403 "$(code -X DELETE "$API/o/$(enc $NAME)")"
want "write outside the record"                     403 "$(code -X POST -H 'Content-Type: text/plain' --data x "$UP?uploadType=media&name=$(enc drop-audit/access-check.txt)")"

[ $bad = 0 ] && echo "all as expected" || echo "NOT as expected: do not give the service its key yet"
exit $bad
