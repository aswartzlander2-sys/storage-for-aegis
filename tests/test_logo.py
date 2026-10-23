"""Original PNG bytes and real alpha in every embedded Windows icon (stdlib)."""
from pathlib import Path
import hashlib
import struct
import unittest
import zlib
from tools.pe_resources import resources

ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA='17765d5e8824bedface16ba8f24ffd7df22761f89ea302084da9b5c2b76c27e8'

def png_alpha(data):
    assert data[:8]==b'\x89PNG\r\n\x1a\n'
    width,height,depth,color,compression,filter_,interlace=struct.unpack_from('>IIBBBBB',data,16)
    assert (depth,color,compression,filter_,interlace)==(8,6,0,0,0),'Expected unflattened 8-bit RGBA PNG'
    position=8;compressed=b''
    while position<len(data):
        size=struct.unpack_from('>I',data,position)[0];kind=data[position+4:position+8]
        if kind==b'IDAT':compressed+=data[position+8:position+8+size]
        position+=size+12
    raw=zlib.decompress(compressed);stride=width*4;assert len(raw)==height*(stride+1)
    previous=bytearray(stride);alpha=bytearray();position=0
    for y in range(height):
        mode=raw[position];row=bytearray(raw[position+1:position+1+stride]);position+=stride+1
        for x in range(stride):
            a=row[x-4] if x>=4 else 0;b=previous[x];c=previous[x-4] if x>=4 else 0
            if mode==0:delta=0
            elif mode==1:delta=a
            elif mode==2:delta=b
            elif mode==3:delta=(a+b)//2
            elif mode==4:
                p=a+b-c;pa,pb,pc=abs(p-a),abs(p-b),abs(p-c);delta=a if pa<=pb and pa<=pc else b if pb<=pc else c
            else:raise AssertionError('Unknown PNG filter')
            row[x]=(row[x]+delta)&255
        alpha.extend(row[3::4]);previous=row
    return width,height,alpha

class TransparentLogoTests(unittest.TestCase):
    def test_uploaded_png_is_unchanged_in_all_runtime_copies(self):
        original=(ROOT/'logo.png').read_bytes();self.assertEqual(hashlib.sha256(original).hexdigest(),SOURCE_SHA)
        self.assertEqual((ROOT/'app/static/cloud-logo.png').read_bytes(),original)
        width,height,alpha=png_alpha(original);self.assertEqual((width,height),(500,500));self.assertEqual(alpha[0],0);self.assertEqual(alpha[width-1],0);self.assertEqual(alpha[-1],0);self.assertIn(255,alpha)
    def test_all_windows_icon_sizes_retain_transparent_background(self):
        res=resources((ROOT/'app/windows/Robo Cloud Enrollment.exe').read_bytes());group=res[(14,'APP',0)];count=struct.unpack_from('<H',group,4)[0];self.assertEqual(count,5)
        for i in range(count):
            w,h,_,_,_,_,_,id_=struct.unpack_from('<BBBBHHIH',group,6+14*i);size=w or 256;data=res[(3,id_,0)]
            with self.subTest(size=size):
                if data.startswith(b'\x89PNG'):
                    width,height,alpha=png_alpha(data)
                else:
                    header,width,height,planes,bits=struct.unpack_from('<IiiHH',data);self.assertEqual(header,40);self.assertEqual(bits,32);height=abs(height)//2
                    alpha=data[header:header+width*height*4][3::4]
                self.assertEqual((width,height),(size,size));self.assertIn(0,alpha);self.assertIn(255,alpha)
                self.assertEqual(alpha[0],0);self.assertEqual(alpha[width-1],0);self.assertEqual(alpha[-1],0)
