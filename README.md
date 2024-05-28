# MapProxy for Docker with MapServer and Mapnik support

![GitHub license](https://img.shields.io/github/license/justb4/docker-mapproxy-mapserver-mapnik)
![GitHub release](https://img.shields.io/github/release/justb4/docker-mapproxy-mapserver-mapnik.svg)
![Docker Pulls](https://img.shields.io/docker/pulls/justb4/mapproxy-mapserver-mapnik.svg)

This image extends the ["justb4" Docker Image for MapProxy with MapServer](https://github.com/justb4/docker-mapproxy-mapserver) with Mapnik binaries.
Reason is that MapProxy supports not only **directly calling the MapServer executable `mapserv`**, i.s.o. of accessing MapServer via OGC WMS but
also supports Mapnik backend. You can also use this image as a regular 
Mapnik Docker Image without running MapProxy. It contains for example the Mapnik Python bindings,
as MapProxy uses.
 

# Image Tags and Versions

Convention: `<mapproxy-version>-<mapserver-version>-<mapnik-version>-<buildnr>`, for example

* `justb4/mapproxy-mapserver-mapnik:1.12.0-7.2.2-3.0.22-1`
* `justb4/mapproxy-mapserver-mapnik:2.0.2-8.0.0-3.1.0-1` etc


# Patches

For optimal performance, patches are applied to `mapnik.py`.
See [patches/README](https://github.com/justb4/docker-mapproxy-mapserver-mapnik/tree/main/patches/README.md).

# How to setup 

The setup is similar as in the ["justb4" Docker Image for MapProxy README](https://github.com/justb4/docker-mapproxy/blob/master/README.md).
Only some extra config is needed for Mapnik. 
Below an example for a `docker-compose` file.

``` 
version: "3"

services:

  mapproxy:

    image: justb4/mapproxy-mapserver-mapnik:latest

    container_name: mapproxy

    environment:
      - MAPPROXY_PROCESSES=4
      - MAPPROXY_THREADS=2
      - UWSGI_EXTRA_OPTIONS=--disable-logging --max-worker-lifetime 30
      - DEBUG=0

    ports:
      - "8086:8080"

    volumes:
      - ./config/mapproxy:/mapproxy
      - ./my-mapnik-dir:/mapnik
      - /var/mapproxy_cache:/mapproxy_cache

``` 

In your MapProxy config YAML you can 
refer to the Mapnik backend binary. 
In the `sources:` section where you would normally configure backend WMS-es:

``` 
sources:
.
.

  my_mapnik_source:
    type: mapnik
    mapfile: /mapnik/my-mapnik-file.xml
    # seed_only: true
    coverage:
      bbox: [ -20000.0,275000.0,300000.0,650000.0 ]
      srs: 'EPSG:28992'

```    


The [Mapproxy Documention](https://mapproxy.org/docs/nightly/sources.html#mapnik) 
shows some alternative config options.
 
# Running Mapnik Directly

Create a `mapnik.sh` script like:

```
#!/bin/bash
#
# usage: mapnik.sh "your commandline"
#

export WORK_DIR=/opt/mapproxy
docker run --rm -v "$(pwd):${WORK_DIR}" -w ${WORK_DIR} -it justb4/mapproxy-mapserver-mapnik:latest sh -c "${@}"
```
 
And then call it like  `mapnik.sh generate-tiles.py`, like [this example](https://github.com/openstreetmap/mapnik-stylesheets/blob/master/generate_tiles.py).
