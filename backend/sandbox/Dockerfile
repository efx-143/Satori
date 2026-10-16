# ─────────────────────────────────────────────────────────────────────────────
# Debug Dojo – Sandbox Execution Image
# ─────────────────────────────────────────────────────────────────────────────
# Security posture (verified against red-team checklist):
#   ✔ Runs as unprivileged UID 65534 (nobody)
#   ✔ All Linux capabilities dropped
#   ✔ No new privileges flag
#   ✔ Custom seccomp profile blocks network, fork, exec, ptrace, mount
#   ✔ Read-only root filesystem (--read-only at runtime)
#   ✔ /tmp is a size-limited tmpfs (noexec, nosuid, nodev)
#   ✔ Hard memory + CPU + PID limits enforced at runtime
#   ✔ No network interface (--network none at runtime)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim-bookworm AS base

# ── System hardening ─────────────────────────────────────────────────────────
# Remove package manager caches and tools that could be used for exfiltration.
RUN apt-get update && \
    apt-get remove -y --purge \
        curl wget netcat-openbsd dnsutils net-tools \
        gcc g++ make build-essential git && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ── Non-root user ─────────────────────────────────────────────────────────────
# UID/GID 65534 = "nobody" — exists in every Linux distro.
RUN groupadd --gid 65534 sandbox && \
    useradd  --uid 65534 --gid 65534 --no-create-home --shell /bin/false sandbox

# ── Execution directory ───────────────────────────────────────────────────────
WORKDIR /runner

# Copy only the entrypoint; everything else stays off the image.
COPY runner_entrypoint.py /runner/runner_entrypoint.py

# Ensure the nobody user owns the runner directory (read) but NOT write.
RUN chown root:sandbox /runner && \
    chmod 750 /runner && \
    chown root:sandbox /runner/runner_entrypoint.py && \
    chmod 440 /runner/runner_entrypoint.py

# ── Switch to non-root ────────────────────────────────────────────────────────
USER sandbox

# ── Entrypoint ────────────────────────────────────────────────────────────────
# Reads a JSON payload from stdin; writes a JSON result to stdout.
# All additional runtime constraints (--read-only, --memory, --network none,
# --pids-limit, --cap-drop ALL, --security-opt) are applied by the host
# TestRunner service when docker run is invoked.
ENTRYPOINT ["python3", "-u", "/runner/runner_entrypoint.py"]
