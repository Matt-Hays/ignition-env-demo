FROM inductiveautomation/ignition:8.1.54@sha256:7b10da23217e755f477cff06b228476fd99d7ffecd0a3850df96af6c5fd3937d

ARG MODULE_FILE

# Cirrus Link acceptance replaces the image-packaged .modl.  The Gateway runs
# as Ignition's non-root user (2003:2003), so both the directory and module
# must remain owned by that user after the derivative-image build.
USER root
COPY --chown=2003:2003 ${MODULE_FILE} /usr/local/bin/ignition/user-lib/modules/
RUN module_path="/usr/local/bin/ignition/user-lib/modules/${MODULE_FILE##*/}" \
    && test -f "$module_path" \
    && chown 2003:2003 /usr/local/bin/ignition/user-lib/modules "$module_path" \
    && chmod 0755 /usr/local/bin/ignition/user-lib/modules \
    && chmod 0644 "$module_path"
USER 2003:2003
