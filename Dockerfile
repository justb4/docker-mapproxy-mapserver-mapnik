FROM justb4/mapproxy-mapserver:1.13.2-7.2.2-2

LABEL maintainer="Just van den Broecke <justb4@gmail.com>"

ARG TIMEZONE="Europe/Amsterdam"
ARG LOCALE="en_US.UTF-8"

ENV TZ=${TIMEZONE} \
    DEBIAN_FRONTEND="noninteractive" \
    DEB_BUILD_DEPS="unzip"  \
    PACKAGES="locales libmapnik-dev mapnik-utils python3-mapnik python3-psycopg2 python3-yaml"  \
    FONT_PACKAGES="fonts-lato fonts-roboto fonts-roboto-slab" \
    FONT_TTF_DIR="/usr/share/fonts/truetype" \
    FONT_MUKTA="Mukta.Font.Family" \
    FONT_MUKTA_VERSION="2.538" \
	LANG=${LOCALE} \
	CHARSET="UTF-8" \
	LC_TIME="C.UTF-8"

# Needed to install
USER root

RUN \
	apt-get update \
	&& apt-get --no-install-recommends install -y ${PACKAGES} ${FONT_PACKAGES} ${DEB_BUILD_DEPS}\
	&& echo "${LANG} ${CHARSET}" > /etc/locale.gen && locale-gen \
    && curl -L -k -v https://github.com/EkType/Mukta/releases/download/${FONT_MUKTA_VERSION}/${FONT_MUKTA}.${FONT_MUKTA_VERSION}.zip > /${FONT_MUKTA}.${FONT_MUKTA_VERSION}.zip \
    && unzip /${FONT_MUKTA}.${FONT_MUKTA_VERSION}.zip -d ${FONT_TTF_DIR}/  \
    && /bin/rm  /${FONT_MUKTA}.${FONT_MUKTA_VERSION}.zip && fc-cache \
    && apt-get remove --purge ${DEB_BUILD_DEPS} -y \
    && apt autoremove -y  \
	&& rm -rf /var/lib/apt/lists/* \
	&& echo "For ${TZ} date=`date`" && echo "Locale=`locale`"

# Use a patched mapnik.py, see patches/README.md for reasons.
COPY patches/mapnik.py /usr/local/lib/python3.7/dist-packages/mapproxy/source/mapnik.py
COPY patches/geopackage.py /usr/local/lib/python3.7/dist-packages/mapproxy/cache/geopackage.py

USER mapproxy
