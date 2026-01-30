#!/usr/bin/env bash
set -euo pipefail

# Print a short summary of non-installed packages (useful for debugging).
print_dpkg_status() {
  echo "[INFO] dpkg status summary:"
  dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' \
    | awk '$1 !~ /^ii/ {print}'
}

# Try to repair apt/dpkg state and purge half-installed agiros packages.
fix_and_clean_broken_agiros() {
  echo "[APT-GUARD] Checking broken dpkg/apt state..."

  DEBIAN_FRONTEND=noninteractive apt-get -f install -y || true
  dpkg --configure -a || true

  broken_pkgs=$(
    dpkg-query -W -f='${db:Status-Abbrev} ${binary:Package}\n' \
      | awk '$1 !~ /^ii/ && $2 ~ /^agiros-pixiu-/' \
      | awk '{print $2}' \
      | sort -u
  )

  if [ -n "${broken_pkgs}" ]; then
    echo "[APT-GUARD][WARN] Found broken agiros packages:"
    echo "${broken_pkgs}"
    DEBIAN_FRONTEND=noninteractive apt-get remove --purge -y ${broken_pkgs} || true
  else
    echo "[APT-GUARD] No broken agiros packages detected."
  fi
}
