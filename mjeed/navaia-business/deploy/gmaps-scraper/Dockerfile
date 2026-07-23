# Fixed image for gosom/google-maps-scraper v1.16.3.
#
# Upstream bug (issue #302): the v1.16.3 binary expects Playwright driver
# 1.60.0 but the image bundles playwright-core 1.61.1, and the runtime
# driver download hits the retired azureedge.net CDN (404). Fix: swap the
# bundled driver package for playwright-core 1.60.0 from npm and install
# its matching Chromium build. Rebuild when upstream ships a real fix.
#
Build:  docker build -t navaia/gmaps-scraper:fixed deploy/gmaps-scraper
Run:    docker run --rm -v "<dir>:/work" navaia/gmaps-scraper:fixed \
    -input /work/queries.txt -results /work/leads_raw.csv \
    -depth 3 -c 2 -geo "24.7136,46.6753" -lang ar -zoom 12 \
    -exit-on-inactivity 3m

# Stage 1: fetch + extract the correct driver package (scraper image has no curl/wget)
FROM busybox AS driver
RUN wget -q -O /tmp/pw.tgz https://registry.npmjs.org/playwright-core/-/playwright-core-1.60.0.tgz \
    && mkdir /pw && tar xzf /tmp/pw.tgz -C /pw

# Stage 2: swap the bundled driver, install the matching Chromium
FROM gosom/google-maps-scraper:v1.16.3
USER root
RUN rm -rf /opt/ms-playwright-go/package
COPY --from=driver /pw/package /opt/ms-playwright-go/package
RUN PLAYWRIGHT_BROWSERS_PATH=/opt/browsers /opt/ms-playwright-go/node /opt/ms-playwright-go/package/cli.js install chromium
