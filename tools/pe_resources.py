"""Small read-only PE resource inspector for build/test verification (stdlib only)."""
import struct

def resources(data):
    pe=struct.unpack_from('<I',data,0x3c)[0]
    assert data[:2]==b'MZ' and data[pe:pe+4]==b'PE\0\0'
    sections=struct.unpack_from('<H',data,pe+6)[0]
    optional=pe+24;optional_size=struct.unpack_from('<H',data,pe+20)[0]
    assert struct.unpack_from('<H',data,optional)[0]==0x20b
    rva,size=struct.unpack_from('<II',data,optional+112+16)
    table=optional+optional_size
    def offset(rva):
        for i in range(sections):
            virtual_size,virtual_address,raw_size,raw_offset=struct.unpack_from('<IIII',data,table+40*i+8)
            if virtual_address<=rva<virtual_address+max(virtual_size,raw_size):
                return raw_offset+rva-virtual_address
        raise ValueError('Unmapped resource RVA')
    root=offset(rva);found={}
    def walk(relative,path):
        assert len(path)<4
        here=root+relative
        named,ids=struct.unpack_from('<HH',data,here+12)
        for i in range(named+ids):
            name,target=struct.unpack_from('<II',data,here+16+8*i)
            if name&0x80000000:
                text=root+(name&0x7fffffff);n=struct.unpack_from('<H',data,text)[0]
                name=data[text+2:text+2+n*2].decode('utf-16le')
            key=path+(name,)
            if target&0x80000000:walk(target&0x7fffffff,key)
            else:
                content,length=struct.unpack_from('<II',data,root+target)
                start=offset(content);assert start+length<=len(data)
                found[key]=data[start:start+length]
    walk(0,())
    return found
