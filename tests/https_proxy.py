"""Test-only TLS reverse proxy. Not shipped as an addon service or a public tunnel."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import http.client
import ssl
import sys
class Proxy(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def route(self):
  if not (self.path.startswith('/agent/') or self.path.startswith('/enroll.sh?')):
   self.send_response(404);self.end_headers();return
  c=http.client.HTTPConnection('127.0.0.1',int(sys.argv[3]),timeout=180)
  body=self.rfile.read(int(self.headers.get('Content-Length',0)))
  c.request(self.command,self.path,body if self.command=='POST' else None,dict(self.headers))
  r=c.getresponse();data=r.read();self.send_response(r.status)
  for k,v in r.getheaders():
   if k.lower() not in ('connection','transfer-encoding','server','date'):self.send_header(k,v)
  self.end_headers();self.wfile.write(data);c.close()
 do_GET=route
 do_POST=route
ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(sys.argv[1],sys.argv[2])
srv=ThreadingHTTPServer(('127.0.0.1',9443),Proxy);srv.socket=ctx.wrap_socket(srv.socket,server_side=True)
print('Test TLS proxy ready',flush=True);srv.serve_forever()
