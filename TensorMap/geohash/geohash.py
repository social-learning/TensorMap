try:
    import _geohash
    import math
except ImportError:
    _geohash = None

__version__ = "0.8.5"
__all__ = ['encode', 'decode', 'decode_exactly', 'bbox', 'neighbors', 'expand']

_base32 = '0123456789bcdefghjkmnpqrstuvwxyz'
_base32_map = {}
for i in range(len(_base32)):
    _base32_map[_base32[i]] = i
del i

LONG_ZERO = 0
import sys

if sys.version_info[0] < 3:
    LONG_ZERO = long(0)


def _float_hex_to_int(f):
    if f < -1.0 or f >= 1.0:
        return None

    if f == 0.0:
        return 1, 1

    h = f.hex()
    x = h.find("0x1.")
    assert (x >= 0)
    p = h.find("p")
    assert (p > 0)

    half_len = len(h[x + 4:p]) * 4 - int(h[p + 1:])
    if x == 0:
        r = (1 << half_len) + ((1 << (len(h[x + 4:p]) * 4)) + int(h[x + 4:p], 16))
    else:
        r = (1 << half_len) - ((1 << (len(h[x + 4:p]) * 4)) + int(h[x + 4:p], 16))

    return r, half_len + 1


def _int_to_float_hex(i, l):
    if l == 0:
        return -1.0

    half = 1 << (l - 1)
    s = int((l + 3) / 4)
    if i >= half:
        i = i - half
        return float.fromhex(("0x0.%0" + str(s) + "xp1") % (i << (s * 4 - l),))
    else:
        i = half - i
        return float.fromhex(("-0x0.%0" + str(s) + "xp1") % (i << (s * 4 - l),))


def _encode_i2c(lat, lon, lat_length, lon_length):
    precision = int((lat_length + lon_length) / 5)
    if lat_length < lon_length:
        a = lon
        b = lat
    else:
        a = lat
        b = lon

    boost = (0, 1, 4, 5, 16, 17, 20, 21)
    ret = ''
    for i in range(precision):
        ret += _base32[(boost[a & 7] + (boost[b & 3] << 1)) & 0x1F]
        t = a >> 3
        a = b >> 2
        b = t

    return ret[::-1]


def encode(latitude, longitude, precision=12):
    if latitude >= 90.0 or latitude < -90.0:
        raise Exception("invalid latitude.")
    while longitude < -180.0:
        longitude += 360.0
    while longitude >= 180.0:
        longitude -= 360.0

    if _geohash:
        basecode = _geohash.encode(latitude, longitude)
        if len(basecode) > precision:
            return basecode[0:precision]
        return basecode + '0' * (precision - len(basecode))

    xprecision = precision + 1
    lat_length = lon_length = int(xprecision * 5 / 2)
    if xprecision % 2 == 1:
        lon_length += 1

    if hasattr(float, "fromhex"):
        a = _float_hex_to_int(latitude / 90.0)
        o = _float_hex_to_int(longitude / 180.0)
        if a[1] > lat_length:
            ai = a[0] >> (a[1] - lat_length)
        else:
            ai = a[0] << (lat_length - a[1])

        if o[1] > lon_length:
            oi = o[0] >> (o[1] - lon_length)
        else:
            oi = o[0] << (lon_length - o[1])

        return _encode_i2c(ai, oi, lat_length, lon_length)[:precision]

    lat = latitude / 180.0
    lon = longitude / 360.0

    if lat > 0:
        lat = int((1 << lat_length) * lat) + (1 << (lat_length - 1))
    else:
        lat = (1 << lat_length - 1) - int((1 << lat_length) * (-lat))

    if lon > 0:
        lon = int((1 << lon_length) * lon) + (1 << (lon_length - 1))
    else:
        lon = (1 << lon_length - 1) - int((1 << lon_length) * (-lon))

    return _encode_i2c(lat, lon, lat_length, lon_length)[:precision]


def _decode_c2i(hashcode):
    lon = 0
    lat = 0
    bit_length = 0
    lat_length = 0
    lon_length = 0
    for i in hashcode:
        t = _base32_map[i]
        if bit_length % 2 == 0:
            lon = lon << 3
            lat = lat << 2
            lon += (t >> 2) & 4
            lat += (t >> 2) & 2
            lon += (t >> 1) & 2
            lat += (t >> 1) & 1
            lon += t & 1
            lon_length += 3
            lat_length += 2
        else:
            lon = lon << 2
            lat = lat << 3
            lat += (t >> 2) & 4
            lon += (t >> 2) & 2
            lat += (t >> 1) & 2
            lon += (t >> 1) & 1
            lat += t & 1
            lon_length += 2
            lat_length += 3

        bit_length += 5

    return (lat, lon, lat_length, lon_length)


def decode(hashcode, delta=False):
    '''
    decode a hashcode and get center coordinate, and distance between center and outer border
    '''
    if _geohash:
        (lat, lon, lat_bits, lon_bits) = _geohash.decode(hashcode)
        latitude_delta = 90.0 / (1 << lat_bits)
        longitude_delta = 180.0 / (1 << lon_bits)
        latitude = lat + latitude_delta
        longitude = lon + longitude_delta
        if delta:
            return latitude, longitude, latitude_delta, longitude_delta
        return latitude, longitude

    (lat, lon, lat_length, lon_length) = _decode_c2i(hashcode)

    if hasattr(float, "fromhex"):
        latitude_delta = 90.0 / (1 << lat_length)
        longitude_delta = 180.0 / (1 << lon_length)
        latitude = _int_to_float_hex(lat, lat_length) * 90.0 + latitude_delta
        longitude = _int_to_float_hex(lon, lon_length) * 180.0 + longitude_delta
        if delta:
            return latitude, longitude, latitude_delta, longitude_delta
        return latitude, longitude

    lat = (lat << 1) + 1
    lon = (lon << 1) + 1
    lat_length += 1
    lon_length += 1

    latitude = 180.0 * (lat - (1 << (lat_length - 1))) / (1 << lat_length)
    longitude = 360.0 * (lon - (1 << (lon_length - 1))) / (1 << lon_length)
    if delta:
        latitude_delta = 180.0 / (1 << lat_length)
        longitude_delta = 360.0 / (1 << lon_length)
        return latitude, longitude, latitude_delta, longitude_delta

    return latitude, longitude


def decode_exactly(hashcode):
    return decode(hashcode, True)


## hashcode operations below

def bbox(hashcode):
    '''
    decode a hashcode and get north, south, east and west border.
    '''
    if _geohash:
        (lat, lon, lat_bits, lon_bits) = _geohash.decode(hashcode)
        latitude_delta = 180.0 / (1 << lat_bits)
        longitude_delta = 360.0 / (1 << lon_bits)
        return {'s': lat, 'w': lon, 'n': lat + latitude_delta, 'e': lon + longitude_delta}

    (lat, lon, lat_length, lon_length) = _decode_c2i(hashcode)
    if hasattr(float, "fromhex"):
        latitude_delta = 180.0 / (1 << lat_length)
        longitude_delta = 360.0 / (1 << lon_length)
        latitude = _int_to_float_hex(lat, lat_length) * 90.0
        longitude = _int_to_float_hex(lon, lon_length) * 180.0
        return {"s": latitude, "w": longitude, "n": latitude + latitude_delta, "e": longitude + longitude_delta}

    ret = {}
    if lat_length:
        ret['n'] = 180.0 * (lat + 1 - (1 << (lat_length - 1))) / (1 << lat_length)
        ret['s'] = 180.0 * (lat - (1 << (lat_length - 1))) / (1 << lat_length)
    else:  # can't calculate the half with bit shifts (negative shift)
        ret['n'] = 90.0
        ret['s'] = -90.0

    if lon_length:
        ret['e'] = 360.0 * (lon + 1 - (1 << (lon_length - 1))) / (1 << lon_length)
        ret['w'] = 360.0 * (lon - (1 << (lon_length - 1))) / (1 << lon_length)
    else:  # can't calculate the half with bit shifts (negative shift)
        ret['e'] = 180.0
        ret['w'] = -180.0

    return ret


def neighbors(hashcode):
    if _geohash and len(hashcode) < 25:
        return _geohash.neighbors(hashcode)

    (lat, lon, lat_length, lon_length) = _decode_c2i(hashcode)
    ret = []
    tlat = lat
    for tlon in (lon - 1, lon + 1):
        code = _encode_i2c(tlat, tlon, lat_length, lon_length)
        if code:
            ret.append(code)

    tlat = lat + 1
    if not tlat >> lat_length:
        for tlon in (lon - 1, lon, lon + 1):
            ret.append(_encode_i2c(tlat, tlon, lat_length, lon_length))

    tlat = lat - 1
    if tlat >= 0:
        for tlon in (lon - 1, lon, lon + 1):
            ret.append(_encode_i2c(tlat, tlon, lat_length, lon_length))

    return ret


def expand(hashcode):
    ret = neighbors(hashcode)
    ret.append(hashcode)
    return ret


def _uint64_interleave(lat32, lon32):
    intr = 0
    boost = (0, 1, 4, 5, 16, 17, 20, 21, 64, 65, 68, 69, 80, 81, 84, 85)
    for i in range(8):
        intr = (intr << 8) + (boost[(lon32 >> (28 - i * 4)) % 16] << 1) + boost[(lat32 >> (28 - i * 4)) % 16]

    return intr


def _uint64_deinterleave(ui64):
    lat = lon = 0
    boost = ((0, 0), (0, 1), (1, 0), (1, 1), (0, 2), (0, 3), (1, 2), (1, 3),
             (2, 0), (2, 1), (3, 0), (3, 1), (2, 2), (2, 3), (3, 2), (3, 3))
    for i in range(16):
        p = boost[(ui64 >> (60 - i * 4)) % 16]
        lon = (lon << 2) + p[0]
        lat = (lat << 2) + p[1]

    return (lat, lon)


def encode_uint64(latitude, longitude):
    if latitude >= 90.0 or latitude < -90.0:
        raise ValueError("Latitude must be in the range of (-90.0, 90.0)")
    while longitude < -180.0:
        longitude += 360.0
    while longitude >= 180.0:
        longitude -= 360.0

    if _geohash:
        ui128 = _geohash.encode_int(latitude, longitude)
        if _geohash.intunit == 64:
            return ui128[0]
        elif _geohash.intunit == 32:
            return (ui128[0] << 32) + ui128[1]
        elif _geohash.intunit == 16:
            return (ui128[0] << 48) + (ui128[1] << 32) + (ui128[2] << 16) + ui128[3]

    lat = int(((latitude + 90.0) / 180.0) * (1 << 32))
    lon = int(((longitude + 180.0) / 360.0) * (1 << 32))
    return _uint64_interleave(lat, lon)


def decode_uint64(ui64):
    if _geohash:
        latlon = _geohash.decode_int(ui64 % 0xFFFFFFFFFFFFFFFF, LONG_ZERO)
        if latlon:
            return latlon

    lat, lon = _uint64_deinterleave(ui64)
    return (180.0 * lat / (1 << 32) - 90.0, 360.0 * lon / (1 << 32) - 180.0)


def expand_uint64(ui64, precision=50):
    ui64 = ui64 & (0xFFFFFFFFFFFFFFFF << (64 - precision))
    lat, lon = _uint64_deinterleave(ui64)
    lat_grid = 1 << (32 - int(precision / 2))
    lon_grid = lat_grid >> (precision % 2)

    if precision <= 2:  # expand becomes to the whole range
        return []

    ranges = []
    if lat & lat_grid:
        if lon & lon_grid:
            ui64 = _uint64_interleave(lat - lat_grid, lon - lon_grid)
            ranges.append((ui64, ui64 + (1 << (64 - precision + 2))))
            if precision % 2 == 0:
                # lat,lon = (1, 1) and even precision
                ui64 = _uint64_interleave(lat - lat_grid, lon + lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision + 1))))

                if lat + lat_grid < 0xFFFFFFFF:
                    ui64 = _uint64_interleave(lat + lat_grid, lon - lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                    ui64 = _uint64_interleave(lat + lat_grid, lon)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                    ui64 = _uint64_interleave(lat + lat_grid, lon + lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
            else:
                # lat,lon = (1, 1) and odd precision
                if lat + lat_grid < 0xFFFFFFFF:
                    ui64 = _uint64_interleave(lat + lat_grid, lon - lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision + 1))))

                    ui64 = _uint64_interleave(lat + lat_grid, lon + lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))

                ui64 = _uint64_interleave(lat, lon + lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision))))
                ui64 = _uint64_interleave(lat - lat_grid, lon + lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision))))
        else:
            ui64 = _uint64_interleave(lat - lat_grid, lon)
            ranges.append((ui64, ui64 + (1 << (64 - precision + 2))))
            if precision % 2 == 0:
                # lat,lon = (1, 0) and odd precision
                ui64 = _uint64_interleave(lat - lat_grid, lon - lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision + 1))))

                if lat + lat_grid < 0xFFFFFFFF:
                    ui64 = _uint64_interleave(lat + lat_grid, lon - lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                    ui64 = _uint64_interleave(lat + lat_grid, lon)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                    ui64 = _uint64_interleave(lat + lat_grid, lon + lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
            else:
                # lat,lon = (1, 0) and odd precision
                if lat + lat_grid < 0xFFFFFFFF:
                    ui64 = _uint64_interleave(lat + lat_grid, lon)
                    ranges.append((ui64, ui64 + (1 << (64 - precision + 1))))

                    ui64 = _uint64_interleave(lat + lat_grid, lon - lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                ui64 = _uint64_interleave(lat, lon - lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision))))
                ui64 = _uint64_interleave(lat - lat_grid, lon - lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision))))
    else:
        if lon & lon_grid:
            ui64 = _uint64_interleave(lat, lon - lon_grid)
            ranges.append((ui64, ui64 + (1 << (64 - precision + 2))))
            if precision % 2 == 0:
                # lat,lon = (0, 1) and even precision
                ui64 = _uint64_interleave(lat, lon + lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision + 1))))

                if lat > 0:
                    ui64 = _uint64_interleave(lat - lat_grid, lon - lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                    ui64 = _uint64_interleave(lat - lat_grid, lon)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                    ui64 = _uint64_interleave(lat - lat_grid, lon + lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
            else:
                # lat,lon = (0, 1) and odd precision
                if lat > 0:
                    ui64 = _uint64_interleave(lat - lat_grid, lon - lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision + 1))))

                    ui64 = _uint64_interleave(lat - lat_grid, lon + lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                ui64 = _uint64_interleave(lat, lon + lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision))))
                ui64 = _uint64_interleave(lat + lat_grid, lon + lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision))))
        else:
            ui64 = _uint64_interleave(lat, lon)
            ranges.append((ui64, ui64 + (1 << (64 - precision + 2))))
            if precision % 2 == 0:
                # lat,lon = (0, 0) and even precision
                ui64 = _uint64_interleave(lat, lon - lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision + 1))))

                if lat > 0:
                    ui64 = _uint64_interleave(lat - lat_grid, lon - lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                    ui64 = _uint64_interleave(lat - lat_grid, lon)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                    ui64 = _uint64_interleave(lat - lat_grid, lon + lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
            else:
                # lat,lon = (0, 0) and odd precision
                if lat > 0:
                    ui64 = _uint64_interleave(lat - lat_grid, lon)
                    ranges.append((ui64, ui64 + (1 << (64 - precision + 1))))

                    ui64 = _uint64_interleave(lat - lat_grid, lon - lon_grid)
                    ranges.append((ui64, ui64 + (1 << (64 - precision))))
                ui64 = _uint64_interleave(lat, lon - lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision))))
                ui64 = _uint64_interleave(lat + lat_grid, lon - lon_grid)
                ranges.append((ui64, ui64 + (1 << (64 - precision))))

    ranges.sort()

    # merge the conditions
    shrink = []
    prev = None
    for i in ranges:
        if prev:
            if prev[1] != i[0]:
                shrink.append(prev)
                prev = i
            else:
                prev = (prev[0], i[1])
        else:
            prev = i

    shrink.append(prev)

    ranges = []
    for i in shrink:
        a, b = i
        if a == 0:
            a = None  # we can remove the condition because it is the lowest value
        if b == 0x10000000000000000:
            b = None  # we can remove the condition because it is the highest value

        ranges.append((a, b))

    return ranges

__base32 = '0123456789bcdefghjkmnpqrstuvwxyz'
__decodemap = { }
for i in range(len(__base32)):
    __decodemap[__base32[i]] = i
del i

def decode(geohash):
    """
    Decode geohash, returning two strings with latitude and longitude
    containing only relevant digits and with trailing zeroes removed.
    """
    lat, lon, lat_err, lon_err = decode_exactly(geohash)
    # Format to the number of decimals that are known
    lats = "%.*f" % (max(1, int(round(-math.log10(lat_err)))) - 1, lat)
    lons = "%.*f" % (max(1, int(round(-math.log10(lon_err)))) - 1, lon)
    if '.' in lats: lats = lats.rstrip('0')
    if '.' in lons: lons = lons.rstrip('0')
    return lats, lons


def decode_exactly(geohash):
    """
    Decode the geohash to its exact values, including the error
    margins of the result.  Returns four float values: latitude,
    longitude, the plus/minus error for latitude (as a positive
    number) and the plus/minus error for longitude (as a positive
    number).
    """
    lat_interval, lon_interval = (-90.0, 90.0), (-180.0, 180.0)
    lat_err, lon_err = 90.0, 180.0
    is_even = True
    for c in geohash:
        cd = __decodemap[c]
        for mask in [16, 8, 4, 2, 1]:
            if is_even: # adds longitude info
                lon_err /= 2
                if cd & mask:
                    lon_interval = ((lon_interval[0]+lon_interval[1])/2, lon_interval[1])
                else:
                    lon_interval = (lon_interval[0], (lon_interval[0]+lon_interval[1])/2)
            else:      # adds latitude info
                lat_err /= 2
                if cd & mask:
                    lat_interval = ((lat_interval[0]+lat_interval[1])/2, lat_interval[1])
                else:
                    lat_interval = (lat_interval[0], (lat_interval[0]+lat_interval[1])/2)
            is_even = not is_even
    lat = (lat_interval[0] + lat_interval[1]) / 2
    lon = (lon_interval[0] + lon_interval[1]) / 2
    return lat, lon, lat_err, lon_err

def encode(latitude, longitude, precision=12):
    """
    Encode a position given in float arguments latitude, longitude to
    a geohash which will have the character count precision.
    """
    lat_interval, lon_interval = (-90.0, 90.0), (-180.0, 180.0)
    geohash = []
    bits = [ 16, 8, 4, 2, 1 ]
    bit = 0
    ch = 0
    even = True
    while len(geohash) < precision:
        if even:
            mid = (lon_interval[0] + lon_interval[1]) / 2
            if longitude > mid:
                ch |= bits[bit]
                lon_interval = (mid, lon_interval[1])
            else:
                lon_interval = (lon_interval[0], mid)
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2
            if latitude > mid:
                ch |= bits[bit]
                lat_interval = (mid, lat_interval[1])
            else:
                lat_interval = (lat_interval[0], mid)
        even = not even
        if bit < 4:
            bit += 1
        else:
            geohash += __base32[ch]
            bit = 0
            ch = 0
    return ''.join(geohash)