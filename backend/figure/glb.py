"""Check that a worker response contains embedded, usable GLB geometry."""

import json
import struct


def validate_glb(data: bytes) -> None:
    try:
        if len(data) < 28 or struct.unpack('<4sII', data[:12]) != (b'glTF', 2, len(data)):
            raise ValueError('Invalid header')
        size, kind = struct.unpack('<I4s', data[12:20])
        if kind != b'JSON' or size % 4 or 20 + size + 8 > len(data):
            raise ValueError('Missing JSON chunk')
        document = json.loads(data[20:20 + size])
        offset = 20 + size
        binary_size, binary_kind = struct.unpack('<I4s', data[offset:offset + 8])
        if binary_kind != b'BIN\0' or offset + 8 + binary_size != len(data):
            raise ValueError('Missing embedded geometry')
        if document['asset']['version'] != '2.0':
            raise ValueError('Unsupported version')
        for item in document.get('buffers', []) + document.get('images', []):
            if 'uri' in item:
                raise ValueError('External resources are not supported')
        has_geometry = False
        for mesh in document['meshes']:
            for primitive in mesh['primitives']:
                accessor = document['accessors'][primitive['attributes']['POSITION']]
                view = document['bufferViews'][accessor['bufferView']]
                count = accessor['count']
                if accessor['type'] != 'VEC3' or accessor['componentType'] != 5126 or count < 3:
                    raise ValueError('Invalid vertex positions')
                start = view.get('byteOffset', 0)
                needed = accessor.get('byteOffset', 0) + (count - 1) * view.get('byteStride', 12) + 12
                if view['buffer'] != 0 or start < 0 or needed > view['byteLength'] or start + view['byteLength'] > binary_size:
                    raise ValueError('Invalid geometry buffer')
                has_geometry = True
        if not has_geometry or not any('mesh' in node for node in document['nodes']):
            raise ValueError('No scene mesh')
    except (KeyError, IndexError, TypeError, ValueError, struct.error, UnicodeError) as error:
        raise ValueError('Invalid or empty GLB geometry') from error
