FROM justb4/mapproxy-mapserver:1.13.2-7.2.2-1

LABEL maintainer="Just van den Broecke <justb4@gmail.com>"

ARG TIMEZONE="Europe/Amsterdam"
ARG LOCALE="en_US.UTF-8"

ENV TZ=${TIMEZONE} \
    DEBIAN_FRONTEND="noninteractive" \
    PACKAGES="locales libmapnik-dev mapnik-utils python3-mapnik python3-psycopg2 python3-yaml python3-watchdog"  \
	LANG=${LOCALE} \
	CHARSET="UTF-8" \
	LC_TIME="C.UTF-8"

# Needed to install
USER root

RUN \
	apt-get update \
	&& apt-get --no-install-recommends install -y ${PACKAGES} \
	&& echo "${LANG} ${CHARSET}" > /etc/locale.gen && locale-gen \
    && apt autoremove -y  \
	&& rm -rf /var/lib/apt/lists/* \
	&& echo "For ${TZ} date=`date`" && echo "Locale=`locale`"

USER mapproxy
