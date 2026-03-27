# 1. BASE IMAGE: Start from the ProteoWizard base
FROM proteowizard/pwiz-skyline-i-agree-to-the-vendor-licenses:latest

# 2. PERMISSIONS
USER root

# 3. DEPENDENCIES
# openjdk postinst expects /usr/share/man/man1 (often missing on slim/minimal bases)
RUN mkdir -p /usr/share/man/man1 \
    && apt-get update && apt-get install -y --no-install-recommends \
    openjdk-8-jre \
    python3 \
    unzip \
    wget \
    curl \
    rsync \
    && rm -rf /var/lib/apt/lists/*

# 4. INSTALL MZmine 2.33
# Official v2.33 release asset (github.com/mzmine/mzmine2)
WORKDIR /opt
RUN wget -q https://github.com/mzmine/mzmine2/releases/download/v2.33/MZmine-2.33.zip \
    && unzip -q MZmine-2.33.zip \
    && rm MZmine-2.33.zip \
    # The zip may unpack into a slightly different folder name (e.g. *-Linux).
    # Locate the actual start script rather than hard-coding the extracted dir.
    && MZDIR="" \
    && for d in /opt/MZmine-2.33* /opt/*MZmine*; do \
         if [ -f "$d/startMZmine_Linux.sh" ]; then MZDIR="$d"; break; fi; \
       done \
    && if [ -z "$MZDIR" ]; then \
         echo "Could not find startMZmine_Linux.sh after unzip" >&2; \
         exit 1; \
       fi \
    && if [ "$MZDIR" != "/opt/MZmine-2.33" ]; then ln -sfn "$MZDIR" /opt/MZmine-2.33; fi \
    && chmod +x /opt/MZmine-2.33/startMZmine_Linux.sh

# 5. ENVIRONMENT
ENV PATH="/opt/MZmine-2.33:${PATH}"

# 6. PIPELINE SCRIPTS
RUN mkdir -p /data /usr/local/share

COPY get_massive_id.py         /usr/local/bin/get_massive_id.py
COPY generate_mzmine_batch.py  /usr/local/bin/generate_mzmine_batch.py
COPY pull_data.sh              /usr/local/bin/pull_data.sh
COPY pipeline.sh               /usr/local/bin/pipeline.sh

# workflow XML is NOT baked in — users mount their own at runtime:
#   -v /path/to/your_workflow.xml:/usr/local/share/metabolomics_workflow.xml

RUN chmod +x \
    /usr/local/bin/get_massive_id.py \
    /usr/local/bin/generate_mzmine_batch.py \
    /usr/local/bin/pull_data.sh \
    /usr/local/bin/pipeline.sh

WORKDIR /data

# 7. EXECUTION
ENTRYPOINT ["/usr/local/bin/pipeline.sh"]