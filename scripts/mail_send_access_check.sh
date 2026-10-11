#!/bin/zsh
# What can the sending side's two accounts do in the draft store's bucket and with the key's secret,
# and what can they not?
#
#   zsh scripts/mail_send_access_check.sh <bucket> <secret name> [root]
#
# Run once after the bucket, its five managed folders, the two accounts and the secret exist
# (mail_send/README.md) and before either service is given a key. It asks as each account, by
# impersonation: no key is made here. For that it lends the caller
# roles/iam.serviceAccountTokenCreator on the account and takes it back at the end, whatever
# happened in between.
#
# The table it holds the bucket to (mail_send/README.md):
#
#                 drafts/         decisions/ results/   grants/    signer-log/   the secret
#   draft window  create, read    read                  create     -             -
#   signing       read            create, read          -          create        read version 1
#
# and for both: nothing replaced, nothing deleted, nothing outside the folders.
#
# It writes a handful of small objects named setup-check-<utc>… under the folders an account may
# create in. They cannot be removed by these accounts — that is the point — and their names are not
# draft names, so the store passes them over. It does not add a version to the secret: making the
# key is the service's own first act. With no key made yet, reading version 1 answers 404 to the
# signing account (allowed to ask, nothing there) and 403 to the draft window's.
#
# Expected: every line ends in "ok". Anything else means the narrowing is not what the README says.
set -u
[ $# -ge 2 ] || { echo "usage: $0 <bucket> <secret name> [root]"; exit 2; }
G=~/google-cloud-sdk/bin/gcloud; P=korean-stock-analyzer; B=$1; SECRET=$2; ROOT=${3:-send}
WINDOW=lxm-mail-draft@$P.iam.gserviceaccount.com
SIGNER=lxm-mail-sign@$P.iam.gserviceaccount.com
ME=$($G config get-value account 2>/dev/null)
API=https://storage.googleapis.com/storage/v1/b/$B
UP=https://storage.googleapis.com/upload/storage/v1/b/$B/o
SM=https://secretmanager.googleapis.com/v1/projects/$P/secrets
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
bad=0; LENT=""

give_back() {
  # The policy keeps the member as the account spells it (capitals and all); `gcloud config` gives it
  # in lower case, and a remove that names it differently finds nothing. So ask the policy for the name.
  local sa m
  for sa in ${=LENT}; do
    m=$($G iam service-accounts get-iam-policy "$sa" --project $P --flatten="bindings[].members" \
          --filter="bindings.role:roles/iam.serviceAccountTokenCreator" --format="value(bindings.members)" 2>/dev/null \
        | grep -i -x "user:$ME" | head -1)
    [ -z "$m" ] && { echo "token role on $sa: none of ours"; continue; }
    $G iam service-accounts remove-iam-policy-binding "$sa" --project $P --member "$m" \
       --role roles/iam.serviceAccountTokenCreator --quiet >/dev/null 2>&1 \
      && echo "token role on $sa taken back" || echo "TOKEN ROLE ON $sa NOT TAKEN BACK: remove it by hand"
  done
}
trap give_back EXIT

token_for() { # account -> TOKEN
  $G iam service-accounts add-iam-policy-binding "$1" --project $P --member "user:$ME" \
     --role roles/iam.serviceAccountTokenCreator --quiet >/dev/null || { echo "could not lend the token role on $1"; exit 2; }
  LENT="$LENT $1"
  TOKEN=""
  for i in $(seq 1 18); do                    # a new binding takes about a minute to be believed
    TOKEN=$($G auth print-access-token --impersonate-service-account "$1" 2>/dev/null)
    [ -n "$TOKEN" ] && break
    sleep 10
  done
  [ -z "$TOKEN" ] && { echo "no token for $1 after 3 minutes"; exit 2; }
  echo; echo "asking as $1 (token not printed)"
}

want() { # label, expected status, got status
  if [ "$2" = "$3" ]; then printf '%-62s HTTP %s  ok\n' "$1" "$3"; else printf '%-62s HTTP %s  EXPECTED %s\n' "$1" "$3" "$2"; bad=1; fi
}
code() { curl -sS -m 30 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" "$@"; }
enc() { python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1],safe=''))" "$1"; }
list() { code "$API/o?prefix=$1&fields=items(name,size,timeCreated,metadata),nextPageToken&maxResults=5"; }
get() { code "$API/o/$(enc $1)?alt=media"; }
put_new() { code -X POST -H 'Content-Type: application/json' --data "{\"kind\":\"setup-check\",\"at\":\"$STAMP\"}" \
                 "$UP?uploadType=media&ifGenerationMatch=0&name=$(enc $1)"; }
put_over() { code -X POST -H 'Content-Type: application/json' --data '{"kind":"setup-check","replaced":true}' \
                  "$UP?uploadType=media&name=$(enc $1)"; }
del() { code -X DELETE "$API/o/$(enc $1)"; }

may_create() { # folder, may it read what it made (200) or not (403)
  local name="$ROOT/$1/setup-check-$STAMP-$2.json"
  want "create $name"                               200 "$(put_new $name)"
  want "  create it again: never replaced"          412 "$(put_new $name)"
  want "  replace it without the condition"         403 "$(put_over $name)"
  want "  delete it"                                403 "$(del $name)"
  want "  read it back"                             "$3" "$(get $name)"
}
may_not_create() { want "create under $ROOT/$1/"   403 "$(put_new $ROOT/$1/setup-check-$STAMP-$2.json)"; }
outside() {
  for p in "" "$ROOT/" "$ROOT/draft" "other/"; do want "list prefix='$p'" 403 "$(list $p)"; done
  want "create outside the folders"                 403 "$(put_new $ROOT/setup-check-$STAMP-$1.json)"
  want "create at the bucket's top"                 403 "$(put_new setup-check-$STAMP-$1.json)"
}

# ── the draft window's account ──
token_for "$WINDOW"
for f in drafts decisions results; do want "list $ROOT/$f/" 200 "$(list $ROOT/$f/)"; done
for f in grants signer-log; do want "list $ROOT/$f/" 403 "$(list $ROOT/$f/)"; done
may_create drafts window 200
may_create grants window 403
for f in decisions results signer-log; do may_not_create $f window; done
outside window
want "read the key's secret"                        403 "$(code "$SM/$SECRET/versions/1:access")"

# ── the signing service's account ──
token_for "$SIGNER"
for f in drafts decisions results; do want "list $ROOT/$f/" 200 "$(list $ROOT/$f/)"; done
for f in grants signer-log; do want "list $ROOT/$f/" 403 "$(list $ROOT/$f/)"; done
want "read what the window placed under drafts/"    200 "$(get $ROOT/drafts/setup-check-$STAMP-window.json)"
may_create decisions signer 200
may_create results signer 200
may_create signer-log signer 403
for f in drafts grants; do may_not_create $f signer; done
outside signer
want "read version 1 of the secret (none made yet)" 404 "$(code "$SM/$SECRET/versions/1:access")"
want "read another secret"                          403 "$(code "$SM/setup-check-no-such-secret/versions/1:access")"
want "list the project's secrets"                   403 "$(code "$SM")"

echo
[ $bad = 0 ] && echo "all as expected" || echo "NOT as expected: do not give a service its key yet"
exit $bad
