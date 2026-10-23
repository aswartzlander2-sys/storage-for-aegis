"""Enrollment packaging, not signing. Never invalidate an existing PE signature."""
import struct
from core import require

DEVELOPER = 'Robo Universal'

def personalize_windows(binary, payload):
    require(isinstance(binary, bytes) and 256 <= len(binary) < 32*1024*1024 and binary[:2] == b'MZ', 'Windows worker template is invalid.', 503)
    pe = struct.unpack_from('<I', binary, 0x3c)[0]
    require(64 <= pe and pe+24+152 <= len(binary) and binary[pe:pe+4] == b'PE\0\0', 'Windows worker PE header is invalid.', 503)
    optional = pe+24
    require(struct.unpack_from('<H', binary, pe+4)[0] == 0x8664 and struct.unpack_from('<H', binary, pe+20)[0] >= 152 and struct.unpack_from('<H', binary, optional)[0] == 0x20b and struct.unpack_from('<I', binary, optional+108)[0] >= 5, 'Windows worker must be Windows/amd64 PE32+.', 503)
    offset, size = struct.unpack_from('<II', binary, optional+112+4*8)
    require(offset == 0 and size == 0, 'Do not personalize a signed template. Sign only the final personalized installer; this download remains unsigned.', 503)
    require(isinstance(payload, bytes) and 1 <= len(payload) <= 16384, 'Invalid enrollment payload.', 503)
    return binary + payload + struct.pack('<I', len(payload)) + b'ROBOCLOUD-ENROLL-V1'
