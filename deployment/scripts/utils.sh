# Exit on error, treat unset variables as an error, and ensure pipeline failures are caught.
set -euo pipefail

# --- Helper Functions ---
log() {
  echo "[INFO] $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

error_exit() {
  echo "[ERROR] $(date '+%Y-%m-%d %H:%M:%S') - $1" >&2
  exit 1
}
