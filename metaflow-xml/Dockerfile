# 1. BASE IMAGE: Start from the ProteoWizard base
FROM proteowizard/pwiz-skyline-i-agree-to-the-vendor-licenses:latest

# 2. PERMISSIONS
USER root

# 3. DEPENDENCIES
RUN apt-get update && apt-get install -y \
    openjdk-8-jre \
    unzip \
    wget \
    curl \
    rsync \
    && rm -rf /var/lib/apt/lists/*

# 4. INSTALL MZmine 2.33
# Using the offoical GitHib archivefor MZmine 2
WORKDIR /opt
RUN wget https://github.com \
&& unzip MZmine-2.33-Linux.zip \
&& rm MZmine-2.33-Linux.zip \
&& chmod +x /opt/MZmine-2.33/startMZmine-Linux.sh

# 5. ENVIRONMENT
# Add MZmine to PATH for access
ENV PATH = "/opt/MZmine-2.33:${PATH}"

# 6. PIPELINE
RUN mkdir /data
WORKDIR /data

COPY pipeline.sh /usr/local/bin/pipeline.sh
RUN chmod +x /usr/local/bin/pipeline.sh

# 7. EXECUTION
ENTRYPOINT ["/usr/local/bin/pipeline.sh"]