# From https://github.com/mapproxy/mapproxy/pull/447 and some 2.0.2 changes TO BE FINALIZED
# Adding conditional multithreading is too involved now. First get stable again.
#
# JvdB: Extend to support reloading Map objects on Mapnik filechanges.
# This file is part of the MapProxy project.
# Copyright (C) 2011 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
import logging

import sys
import os
import time
import threading
import multiprocessing
from io import BytesIO

from mapproxy.grid import tile_grid
from mapproxy.image import ImageSource
from mapproxy.image.opts import ImageOptions
from mapproxy.layer import MapExtent, DefaultMapExtent, BlankImage, MapLayer
from mapproxy.source import  SourceError
from mapproxy.client.log import log_request
from mapproxy.util.py import reraise_exception
from mapproxy.util.async_ import run_non_blocking

# Use Python-based polling Observer, should be ok
from watchdog.observers.polling import PollingObserver as Observer

# This gave issues on Ubuntu, eating to many inotify instances
# from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    import mapnik
    mapnik
except ImportError:
    try:
        # for 2.0 alpha/rcs and first 2.0 release
        import mapnik2 as mapnik
    except ImportError:
        mapnik = None

try:
    import queue
    Queue = queue.Queue
    Empty = queue.Empty
    Full = queue.Full
except ImportError:  # in python2 it is called Queue
    import Queue
    Empty = Queue.Empty
    Full = Queue.Full
MAX_UNUSED_MAPS = 10

# fake 2.0 API for older versions
if mapnik and not hasattr(mapnik, 'Box2d'):
    mapnik.Box2d = mapnik.Envelope

log = logging.getLogger(__package__)

# Listens to changes in directory of Mapnik config file.
class FileChangeEventHandler(FileSystemEventHandler):
    def __init__(self):
        log.info('Start FileChangeEventHandler')

    def on_any_event(self, event):
        log.info('Changed %s - clear cache' % event.src_path)
        self.clear_cache()

    def start_listen(self, mapfile, map_objs, map_objs_queues):
        self.map_objs = map_objs
        self.map_objs_queues = map_objs_queues
        self.observer = Observer()
        self.observer.schedule(_event_handler, os.path.dirname(mapfile), recursive=True)
        self.observer.start()

    def clear_cache(self):
        # Clear all cached Mapnik Map objects and the queues.
        # MAY NOT BE THREAD SAFE, BUT MAINLY USED FOR DEVELOPMENT
        try:
            # log.info('Wait for _map_objs_lock...')
            # with _map_objs_lock:
            log.info('Going through _map_objs len=%d' % len(self.map_objs))
            for cachekey in list(self.map_objs.keys()):
                # log.info('Clearing cache key=%s...' % str(cachekey))
                try:
                    for queue_cachekey in list(self.map_objs_queues.keys()):
                        del self.map_objs[queue_cachekey]
                        self.map_objs_queues[queue_cachekey] = Queue(MAX_UNUSED_MAPS)
                        # log.info('Clearing queue key=%s' % str(queue_cachekey))

                    mapnik_map = self.map_objs[cachekey]
                    mapnik_map.remove_all()
                    mapnik.clear_cache()
                    del self.map_objs[cachekey]
                    # log.info('Cleared cache key=%s' % str(cachekey))
                except Exception as e:
                    log.info('Exception! %s' % str(e))
                    continue

            self.map_objs = {}
            self.map_objs_queues = {}
            self.observer.stop()
        except Exception as err:
            log.info('Exception! %s' % str(err))


class MapnikSource(MapLayer):
    supports_meta_tiles = True

    def __init__(self, mapfile, layers=None, image_opts=None, coverage=None,
                 res_range=None, lock=None, reuse_map_objects=False,
                 scale_factor=None, multithreaded=False):
        MapLayer.__init__(self, image_opts=image_opts)
        self.mapfile = mapfile
        self.coverage = coverage
        self.res_range = res_range
        self.layers = set(layers) if layers else None
        self.scale_factor = scale_factor
        self.lock = lock
        self.multithreaded = multithreaded
        self._cache_map_obj = reuse_map_objects
        if self.coverage:
            self.extent = MapExtent(self.coverage.bbox, self.coverage.srs)
        else:
            self.extent = DefaultMapExtent()
        # global objects allow caching over multiple instances within the same worker process
        global _map_objs # mapnik map objects by cachekey
        _map_objs = {}
        global _map_objs_lock
        _map_objs_lock = threading.Lock()
        global _map_objs_queues # queues of unused mapnik map objects by PID and mapfile
        _map_objs_queues = {}

        # Start handler to listen to file change events in Mapnik dir.
        global _event_handler
        _event_handler = FileChangeEventHandler()

    def get_map(self, query):
        if self.res_range and not self.res_range.contains(query.bbox, query.size,
                                                          query.srs):
            raise BlankImage()
        if self.coverage and not self.coverage.intersects(query.bbox, query.srs):
            raise BlankImage()

        try:
            resp = self.render(query)
        except RuntimeError as ex:
            log.error('could not render Mapnik map: %s', ex)
            reraise_exception(SourceError(ex.args[0]), sys.exc_info())
        resp.opacity = self.opacity
        return resp

    def render(self, query):
        mapfile = self.mapfile
        if '%(webmercator_level)' in mapfile:
            _bbox, level = tile_grid(3857).get_affected_bbox_and_level(
                query.bbox, query.size, req_srs=query.srs)
            mapfile = mapfile % {'webmercator_level': level}

        if self.lock:
            with self.lock():
                return self.render_mapfile(mapfile, query)
        else:
            return self.render_mapfile(mapfile, query)

    def _create_map_obj(self, mapfile, process_id):
        m = mapnik.Map(0, 0)
        mapnik.load_map(m, str(mapfile))
        m.map_obj_pid = process_id
        return m

    def _get_map_obj(self, mapfile):
        process_id = multiprocessing.current_process()._identity
        queue_cachekey = (process_id, mapfile)
        if queue_cachekey in _map_objs_queues:
            try:
                m = _map_objs_queues[queue_cachekey].get_nowait()
                # check explicitly for the process ID to ensure that
                # map objects cannot move between processes
                if m.map_obj_pid == process_id:
                    return m
            except Empty:
                pass
        return self._create_map_obj(mapfile, process_id)

    def _put_unused_map_obj(self, mapfile, m):
        process_id = multiprocessing.current_process()._identity
        queue_cachekey = (process_id, mapfile)
        if queue_cachekey not in _map_objs_queues:
            _map_objs_queues[queue_cachekey] = Queue(MAX_UNUSED_MAPS)
        try:
            _map_objs_queues[queue_cachekey].put_nowait(m)
        except Full:
            # cleanup the data and drop the map, so it can be garbage collected
            m.remove_all()
            mapnik.clear_cache()

    def _get_cachekey(self, mapfile):
        if self._cache_map_obj:
            # all MapnikSources with the same mapfile share the same Mapnik Map.
            return (None, None, mapfile)
        thread_id = threading.current_thread().ident
        process_id = multiprocessing.current_process()._identity
        return (process_id, thread_id, mapfile)

    def _cleanup_unused_cached_maps(self, mapfile):
        # clean up no longer used cached maps
        process_id = multiprocessing.current_process()._identity
        process_cache_keys = [k for k in _map_objs.keys()
                              if k[0] == process_id]
        # To avoid time-consuming cleanup whenever one thread in the
        # threadpool finishes, allow ignoring up to 5 dead mapnik
        # instances.  (5 is empirical)
        if len(process_cache_keys) > (5 + threading.active_count()):
            active_thread_ids = set(i.ident for i in threading.enumerate())
            for k in process_cache_keys:
                with _map_objs_lock:
                    if not k[1] in active_thread_ids and k in _map_objs:
                        try:
                            m = _map_objs[k]
                            del _map_objs[k]
                            # put the map into the queue of unused
                            # maps so it can be re-used from another
                            # thread.
                            self._put_unused_map_obj(mapfile, m)
                        except KeyError:
                            continue

    def map_obj(self, mapfile):
        if len(_map_objs) == 0:
            _event_handler.start_listen(mapfile, _map_objs, _map_objs_queues )

        # cache loaded map objects
        # only works when a single proc/thread accesses the map
        # (forking the render process doesn't work because of open database
        #  file handles that gets passed to the child)
        # segment the cache by process and thread to avoid interference
        cachekey = self._get_cachekey(mapfile)
        with _map_objs_lock:
            if cachekey not in _map_objs:
                log.info('New map object key=%s' % str(cachekey))
                _map_objs[cachekey] = self._get_map_obj(mapfile)

            mapnik_map = _map_objs[cachekey]

        self._cleanup_unused_cached_maps(mapfile)

        return mapnik_map

    def render_mapfile(self, mapfile, query):
        return run_non_blocking(self._render_mapfile, (mapfile, query))

    def _render_mapfile(self, mapfile, query):
        start_time = time.time()

        m = self.map_obj(mapfile)
        m.resize(query.size[0], query.size[1])
        # m.srs = '+init=%s' % str(query.srs.srs_code.lower())
        m.srs = str(query.srs.srs_code.lower())
        envelope = mapnik.Box2d(*query.bbox)
        m.zoom_to_box(envelope)
        data = None

        try:
            if self.layers:
                i = 0
                for layer in m.layers[:]:
                    if layer.name != 'Unknown' and layer.name not in self.layers:
                        del m.layers[i]
                    else:
                        i += 1

            img = mapnik.Image(query.size[0], query.size[1])
            if self.scale_factor:
                mapnik.render(m, img, self.scale_factor)
            else:
                mapnik.render(m, img)
            data = img.tostring(str(query.format))
        finally:
            size = None
            if data:
                size = len(data)
            log_request('%s:%s:%s:%s' % (mapfile, query.bbox, query.srs.srs_code, query.size),
                        status='200' if data else '500', size=size, method='API', duration=time.time()-start_time)

        return ImageSource(BytesIO(data), size=query.size,
                           image_opts=ImageOptions(format=query.format))
