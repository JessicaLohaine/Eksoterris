"""Official scientific sources, immutable raw cache and provenance."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import time
import ssl
import os
import zipfile
import truststore
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, quote, urlparse
from urllib.request import Request, urlopen, build_opener, HTTPSHandler, HTTPRedirectHandler

import numpy as np

DATA = Path(__file__).parent / 'data'
DATA.mkdir(exist_ok=True)
MOON_BASE = 'https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/'
MARS_BASE = 'https://pds-geosciences.wustl.edu/mgs/urn-nasa-pds-mgs_mola_topography_derived/meg004/'
ETOPO = 'https://oceanwatch.aoml.noaa.gov/erddap/griddap/etopo180.csv'


class ScientificRedirectHandler(HTTPRedirectHandler):
    """Avoid forwarding Earthdata bearer credentials to other domains."""
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        destination = urlparse(newurl)
        if redirected and (destination.scheme != 'https' or destination.hostname not in {
                'data.lpdaac.earthdatacloud.nasa.gov', 'urs.earthdata.nasa.gov'}):
            redirected.remove_header('Authorization')
        return redirected


def fetch(url: str, extension: str = 'bin', headers=None, magic=None) -> tuple[bytes, dict]:
    """Cache exact server bytes and restrict optional Earthdata credentials."""
    if headers and any(name.lower() == 'authorization' for name in headers):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'data.lpdaac.earthdatacloud.nasa.gov':
            raise ValueError('Earthdata authorization is restricted to HTTPS LP DAAC downloads.')
    key = hashlib.sha256(url.encode()).hexdigest()
    path = DATA / f'{key}.{extension}'
    manifest = DATA / f'{key}.meta.json'
    if path.exists() and manifest.exists():
        raw = path.read_bytes()
        meta = json.loads(manifest.read_text())
        if hashlib.sha256(raw).hexdigest() == meta['sha256'] and (not magic or raw.startswith(magic)):
            return raw, meta
        raise ValueError('Cached source checksum mismatch; reacquisition required.')
    last_error = None
    for attempt in range(3):
        try:
            req = Request(url, headers={'User-Agent': 'Eksoterris/1.0 (scientific research prototype)', **(headers or {})})
            opener = build_opener(HTTPSHandler(context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)), ScientificRedirectHandler())
            with opener.open(req, timeout=45) as response:
                raw = response.read(40_000_001)
            if len(raw) > 40_000_000:
                raise ValueError('Source exceeds the configured download limit.')
            if magic and not raw.startswith(magic):
                raise ValueError('The server did not return the expected scientific file; Earthdata Login may be required.')
            meta = {'url': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
                    'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
            path.write_bytes(raw)
            manifest.write_text(json.dumps(meta, indent=2), encoding='utf-8')
            return raw, meta
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1 + attempt)
    raise RuntimeError(f'Source acquisition failed ({url.split("?")[0]}): {last_error}')


def field(label: str, name: str) -> str:
    match = re.search(r'^\s*' + re.escape(name) + r'\s*=\s*([^\r\n]+)', label, re.M)
    if not match:
        raise ValueError(f'Missing PDS label field: {name}')
    return match.group(1).strip().strip('"').split(' <')[0]


class Raster:
    def __init__(self, values, latitudes, longitudes, provenance, global_longitude=False):
        self.z = np.asarray(values, dtype=float)
        self.lat = np.asarray(latitudes, dtype=float)
        self.lon = np.asarray(longitudes, dtype=float)
        self.provenance = provenance
        self.wrap = global_longitude
        if self.z.shape != (len(self.lat), len(self.lon)) or not np.isfinite(self.z).all():
            raise ValueError('Invalid raster dimensions or missing elevation samples.')
        for axis in (self.lat, self.lon):
            if len(axis)<2 or not np.isfinite(axis).all() or np.any(np.diff(axis)<=0) or not np.allclose(np.diff(axis),axis[1]-axis[0],rtol=1e-5,atol=1e-8):
                raise ValueError('Raster coordinates must be finite, ascending and regularly spaced.')

    def sample(self, lat, lon):
        """Bilinear interpolation on ascending regular geographic axes."""
        lat, lon = np.asarray(lat), np.asarray(lon)
        dy, dx = self.lat[1] - self.lat[0], self.lon[1] - self.lon[0]
        y = (lat - self.lat[0]) / dy
        x = (lon - self.lon[0]) / dx
        if self.wrap:
            x %= len(self.lon)
        if np.any(y < 0) or np.any(y > len(self.lat)-1) or (not self.wrap and (np.any(x < 0) or np.any(x > len(self.lon)-1))):
            raise ValueError('Requested sample outside source coverage.')
        iy = np.minimum(y.astype(int), len(self.lat)-2)
        ix = np.minimum(x.astype(int), len(self.lon)-1 if self.wrap else len(self.lon)-2)
        jy = iy + 1
        jx = (ix + 1) % len(self.lon)
        fy, fx = y - iy, x - ix
        return ((1-fy)*((1-fx)*self.z[iy, ix] + fx*self.z[iy, jx])
                + fy*((1-fx)*self.z[jy, ix] + fx*self.z[jy, jx]))


def planetary_raster(body: str) -> Raster:
    if body == 'moon':
        base, name, title = MOON_BASE, 'LDEM_4', 'NASA LRO LOLA GDR LDEM_4 V3.0'
        label_ext, img_ext = '.LBL', '.IMG'
    elif body == 'mars':
        base, name, title = MARS_BASE, 'megt90n000cb', 'NASA MGS MOLA MEGDR topography, 4 pixels/degree'
        label_ext, img_ext = '.lbl', '.img'
    else:
        raise ValueError('Unsupported planetary body.')
    label_raw, label_meta = fetch(base + name + label_ext, 'lbl')
    label = label_raw.decode('ascii')
    raw, meta = fetch(base + name + img_ext, 'img')
    rows, cols = int(field(label, 'LINES')), int(field(label, 'LINE_SAMPLES'))
    ppd = float(field(label, 'MAP_RESOLUTION'))
    bits, sample_type = int(field(label, 'SAMPLE_BITS')), field(label, 'SAMPLE_TYPE')
    if (rows != 720 or cols != 1440 or ppd != 4 or
            field(label,'POSITIVE_LONGITUDE_DIRECTION') != 'EAST' or
            float(field(label,'WESTERNMOST_LONGITUDE')) != 0 or
            float(field(label,'EASTERNMOST_LONGITUDE')) != 360):
        raise ValueError('Unsupported planetary grid registration.')
    if bits != 16 or sample_type not in ('LSB_INTEGER', 'MSB_INTEGER'):
        raise ValueError('Unsupported PDS sample format.')
    if len(raw) != rows * cols * 2:
        raise ValueError('PDS data size does not match label.')
    values = np.frombuffer(raw, dtype='<i2' if sample_type == 'LSB_INTEGER' else '>i2').reshape(rows, cols)
    if np.any(values == -32768):
        raise ValueError('Missing PDS pixels require a coverage mask.')
    scale = float(field(label, 'SCALING_FACTOR')) if re.search(r'^\s*SCALING_FACTOR\s*=', label, re.M) else 1.0
    # LOLA's OFFSET is the reference sphere radius, NOT an elevation offset.
    values = values.astype(float) * scale
    meta.update(id=body + '-elevation', title=title, label=label_meta,
                unit='m', pixels_per_degree=ppd,
                datum='1737.4 km reference sphere' if body == 'moon' else 'MOLA areoid',
                coordinate_system='Mean Earth/polar axis DE421' if body == 'moon' else 'MOLA planetocentric east-positive',
                reference_radius_m=float(field(label,'A_AXIS_RADIUS'))*1000,
                note='Absolute elevations across bodies are excluded from the similarity calculation.')
    return Raster(values[::-1], -90 + (np.arange(rows)+0.5)/ppd,
                  (np.arange(cols)+0.5)/ppd, meta, True)


def mola_observation_counts():
    """Load the optional, co-registered MEGDR shot-count map without interpolating counts."""
    name = 'megc90n000cb'
    label_url, image_url = MARS_BASE + name + '.lbl', MARS_BASE + name + '.img'
    # The companion grid is optional. Do not delay or fail a scientific analysis
    # when it has not been acquired and checksum-verified in the local cache.
    if not all((DATA / (hashlib.sha256(url.encode()).hexdigest() + ext)).exists()
               for url, ext in ((label_url, '.lbl'), (image_url, '.img'))):
        return None
    label_raw, label_meta = fetch(label_url, 'lbl')
    raw, image_meta = fetch(image_url, 'img')
    topo_label, _ = fetch(MARS_BASE + 'megt90n000cb.lbl', 'lbl')
    label, topo = label_raw.decode('ascii'), topo_label.decode('ascii')
    registration = ('LINES', 'LINE_SAMPLES', 'MAP_RESOLUTION', 'MAP_PROJECTION_TYPE',
                    'POSITIVE_LONGITUDE_DIRECTION', 'WESTERNMOST_LONGITUDE',
                    'EASTERNMOST_LONGITUDE', 'MINIMUM_LATITUDE', 'MAXIMUM_LATITUDE',
                    'A_AXIS_RADIUS', 'B_AXIS_RADIUS', 'C_AXIS_RADIUS',
                    'CENTER_LATITUDE', 'CENTER_LONGITUDE', 'MAP_PROJECTION_ROTATION',
                    'LINE_FIRST_PIXEL', 'LINE_LAST_PIXEL',
                    'SAMPLE_FIRST_PIXEL', 'SAMPLE_LAST_PIXEL',
                    'LINE_PROJECTION_OFFSET', 'SAMPLE_PROJECTION_OFFSET',
                    'COORDINATE_SYSTEM_NAME')
    if any(field(label, key) != field(topo, key) for key in registration):
        raise ValueError('MOLA count and topography map registrations differ.')
    rows, cols = int(field(label, 'LINES')), int(field(label, 'LINE_SAMPLES'))
    if (rows, cols) != (720, 1440) or field(label, 'SAMPLE_TYPE') != 'MSB_INTEGER' or field(label, 'SAMPLE_BITS') != '16' or len(raw) != rows * cols * 2:
        raise ValueError('Unexpected MOLA observation-count format.')
    counts = np.frombuffer(raw, dtype='>i2').reshape(rows, cols)
    if np.any(counts < 0):
        raise ValueError('Negative MOLA observation counts require separate interpretation.')
    return counts[::-1], {'image': image_meta, 'label': label_meta}


def earth_raster(latitude: float, longitude: float) -> Raster:
    # +/- 2 degrees latitude and a longitude margin cover the 220 km local grid.
    delta_lon = 2.0 / np.cos(np.radians(latitude))
    south, north = latitude-2.0, latitude+2.0
    west, east = longitude-delta_lon, longitude+delta_lon
    query = f'altitude[({south:.5f}):1:({north:.5f})][({west:.5f}):1:({east:.5f})]'
    raw, meta = fetch(ETOPO + '?' + quote(query, safe='(),:'), 'csv')
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8'))))
    if not rows or rows[0] != ['latitude', 'longitude', 'altitude']:
        raise ValueError('Unexpected NOAA raster columns.')
    if rows[1] != ['degrees_north','degrees_east','m']:
        raise ValueError('Unexpected NOAA coordinates or elevation units.')
    samples = np.asarray([[float(c) for c in row] for row in rows[2:] if row], dtype=float)
    lats, lons = np.unique(samples[:, 0]), np.unique(samples[:, 1])
    values = np.full((len(lats), len(lons)), np.nan)
    values[np.searchsorted(lats, samples[:, 0]), np.searchsorted(lons, samples[:, 1])] = samples[:, 2]
    meta.update(id='earth-elevation-' + meta['sha256'][:12], title='NOAA ETOPO1 Ice Surface, 1 arc-minute',
                unit='m', datum='Mean sea level', pixels_per_degree=60,
                citation='https://doi.org/10.7289/V5C8276M',
                note='Official NOAA composite including NASA SRTM30; not the SRTMGL1 30 m product.')
    return Raster(values, lats, lons, meta)


def earth_climate(latitude, longitude):
    params = {'parameters':'T2M,PRECTOTCORR,PS', 'community':'AG', 'latitude':latitude,
              'longitude':longitude, 'format':'JSON'}
    raw, meta = fetch('https://power.larc.nasa.gov/api/temporal/climatology/point?' + urlencode(params), 'json')
    data = json.loads(raw)
    values = {k: v.get('ANN') for k, v in data['properties']['parameter'].items()}
    if any(v is None or v == data.get('header', {}).get('fill_value', -999) for v in values.values()):
        raise ValueError('NASA POWER returned missing annual climate values.')
    meta.update(id='nasa-power-' + meta['sha256'][:12], title='NASA POWER climatology',
                parameters=data.get('parameters', {}), header=data.get('header', {}))
    return {'annual': values, 'provenance': meta,
            'usage': 'Earth context only; excluded from cross-body topographic distance.'}


def srtm_catalog():
    url = 'https://cmr.earthdata.nasa.gov/search/collections.json?' + urlencode({'short_name':'SRTMGL1', 'version':'003', 'page_size':3})
    raw, meta = fetch(url, 'json')
    entries = json.loads(raw)['feed']['entry']
    return {'source': meta, 'collections': [{'id':e['id'], 'title':e['title'], 'links':e.get('links', [])} for e in entries],
            'status':'Catalog metadata only. SRTMGL1 granule downloads may require Earthdata Login.'}


def srtm_granules(latitude, longitude):
    """Discover actual 30 m granules at a point in NASA Earthdata CMR."""
    if not -60 <= latitude <= 60 or not -180 <= longitude <= 180:
        raise ValueError('SRTM point must be within approximately 60 degrees latitude and valid longitude.')
    url='https://cmr.earthdata.nasa.gov/search/granules.json?' + urlencode({
        'short_name':'SRTMGL1','version':'003','point':f'{longitude},{latitude}','page_size':10})
    raw,meta=fetch(url,'json')
    entries=json.loads(raw)['feed']['entry']
    return {'source':meta,'granules':[{'id':e['id'],'title':e['title'],
             'producer_granule_id':e.get('producer_granule_id'),
             'download_links':[link['href'] for link in e.get('links',[])
                if link.get('rel','').endswith('/data#') and link.get('href','').startswith('https://data.lpdaac.earthdatacloud.nasa.gov/')]
             } for e in entries], 'status':'Granule metadata and protected download links; the raster is not yet downloaded.'}


def srtm_tile_origin(filename):
    """Recover the southern and western integer-degree HGT tile edges."""
    name = filename.split('/')[-1].upper()
    match = re.fullmatch(r'([NS])(\d{2})([EW])(\d{3})(?:\.SRTMGL1)?\.HGT', name)
    if not match:
        raise ValueError('Unexpected SRTM tile georeferencing name.')
    south = int(match[2]) * (1 if match[1] == 'N' else -1)
    west = int(match[4]) * (1 if match[3] == 'E' else -1)
    return south, west


def sample_srtm(latitude, longitude):
    """Read a single authenticated SRTMGL1 HGT tile and sample an actual pixel."""
    token=os.getenv('EARTHDATA_TOKEN','').strip()
    if not token:
        raise ValueError('EARTHDATA_TOKEN is required to download the protected LP DAAC SRTM granule.')
    granules=srtm_granules(latitude,longitude)['granules']
    matches=[g for g in granules if g['download_links']]
    if not matches: raise ValueError('CMR found no downloadable SRTMGL1 tile for this coordinate.')
    tile=matches[0]
    raw,meta=fetch(tile['download_links'][0],'zip',headers={'Authorization':'Bearer '+token},magic=b'PK')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members=[member for member in archive.infolist() if member.filename.lower().endswith('.hgt')]
        if len(members)!=1 or members[0].file_size != 3601*3601*2:
            raise ValueError('SRTM archive does not contain exactly one 3601 by 3601 signed 16-bit HGT grid.')
        hgt=np.frombuffer(archive.read(members[0]),dtype='>i2').reshape(3601,3601)
    south,west=srtm_tile_origin(members[0].filename)
    row=round((south+1-latitude)*3600)
    col=round((longitude-west)*3600)
    if not 0<=row<=3600 or not 0<=col<=3600:
        raise ValueError('Discovered tile does not cover requested point.')
    elevation=int(hgt[row,col])
    if elevation == -32768: raise ValueError('The requested SRTM pixel is void (missing).')
    return {'latitude':south+1-row/3600,'longitude':west+col/3600,
            'elevation_m':elevation,'native_spacing_arc_seconds':1,
            'datum':'EGM96 geoid','source':{'granule':tile,'download':meta},
            'usage':'Pixel inspection only; regional KNN currently uses NOAA ETOPO1.'}
