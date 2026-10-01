# Load generator for the benchmark. The version is pinned and must match the
# JMeter GUI used on Windows to inspect/edit the .jmx files.
FROM eclipse-temurin:21-jre-jammy

ARG JMETER_VERSION=5.6.3
ARG JMETER_URL=https://archive.apache.org/dist/jmeter/binaries

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && cd /tmp \
    && curl -fsSLO "${JMETER_URL}/apache-jmeter-${JMETER_VERSION}.tgz" \
    && curl -fsSLO "${JMETER_URL}/apache-jmeter-${JMETER_VERSION}.tgz.sha512" \
    && echo "$(cut -d' ' -f1 apache-jmeter-${JMETER_VERSION}.tgz.sha512)  apache-jmeter-${JMETER_VERSION}.tgz" | sha512sum -c - \
    && tar -xzf "apache-jmeter-${JMETER_VERSION}.tgz" -C /opt \
    && mv "/opt/apache-jmeter-${JMETER_VERSION}" /opt/jmeter \
    && rm -f /tmp/apache-jmeter-*

ENV PATH="/opt/jmeter/bin:${PATH}"
WORKDIR /tests

ENTRYPOINT ["jmeter"]
CMD ["--version"]
