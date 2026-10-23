"""Branding is not authentication; current downloads stay explicitly unsigned."""
import base64
import json
from pathlib import Path
import shlex
import struct
import subprocess
import unittest
import test_enrollment
from core import Problem
from installers import DEVELOPER,personalize_windows

ROOT=Path(__file__).resolve().parents[1]

class SigningPackagingTests(unittest.TestCase):
    def test_unsigned_template_can_be_personalized_without_touching_prefix(self):
        binary=(ROOT/'app/windows/Robo Cloud Enrollment.exe').read_bytes();payload=b'{"test":"not-a-real-capability"}'
        artifact=personalize_windows(binary,payload);self.assertEqual(artifact[:len(binary)],binary);self.assertTrue(artifact.endswith(b'ROBOCLOUD-ENROLL-V1'));self.assertEqual(DEVELOPER,'Robo Universal')
    def test_signed_or_inconsistent_certificate_directory_is_rejected(self):
        raw=(ROOT/'app/windows/Robo Cloud Enrollment.exe').read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0];entry=pe+24+112+32
        for offset,size in [(len(raw),8),(len(raw),0),(0,8)]:
            binary=bytearray(raw);struct.pack_into('<II',binary,entry,offset,size)
            with self.assertRaises(Problem) as e:personalize_windows(bytes(binary),b'{}')
            self.assertEqual(e.exception.status,503);self.assertIn('signed template',str(e.exception))
    def test_malformed_templates_and_oversized_payloads_fail_closed(self):
        for raw in [b'MZ',b'x'*1024,b'MZ'+bytes(1022)]:
            with self.assertRaises(Problem):personalize_windows(raw,b'{}')
        raw=(ROOT/'app/windows/Robo Cloud Enrollment.exe').read_bytes()
        for payload in [b'',b'x'*16385]:
            with self.assertRaises(Problem):personalize_windows(raw,payload)
    def test_build_record_is_unsigned_not_a_verified_publisher_claim(self):
        record=json.loads((ROOT/'docs/WINDOWS-BUILD.json').read_text());self.assertIs(record['signed'],False);self.assertEqual(record['companyName'],'Robo Universal');self.assertIn('metadata only',record['signingStatus'])
    def test_linux_signer_syntax_and_argument_guard(self):
        script=ROOT/'tools/sign_linux_enrollment.sh';self.assertEqual(subprocess.run(['bash','-n',str(script)],capture_output=True).returncode,0)
        result=subprocess.run(['bash',str(script)],capture_output=True,text=True);self.assertEqual(result.returncode,2);self.assertIn('FULL_SIGNING_KEY_FINGERPRINT',result.stderr)

class DeveloperBrandingHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):test_enrollment.EnrollmentHTTPTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):test_enrollment.EnrollmentHTTPTests.tearDownClass.__func__(cls)
    call=test_enrollment.EnrollmentHTTPTests.call
    route=test_enrollment.EnrollmentHTTPTests.route
    def test_both_served_logo_routes_are_exact_transparent_upload(self):
        import hashlib
        for route in ('/assets/logo.png','/assets/cloud-logo.png'):
            status,body=self.call(route);self.assertEqual(status,200,body[:50]);self.assertEqual(hashlib.sha256(body).hexdigest(),'17765d5e8824bedface16ba8f24ffd7df22761f89ea302084da9b5c2b76c27e8')
    def test_generated_linux_script_has_developer_and_unsigned_notice(self):
        self.route();code,data=self.call('/api/groups',{'name':'Developer branding','sub':'developer-branding'});self.assertEqual(code,200,data);gid=json.loads(data)['group']['id']
        code,data=self.call('/api/groups/'+gid+'/servers',{'kind':'linux','name':'Linux branding','path':'~/robo-branding'});sid=json.loads(data)['server']['id']
        code,data=self.call('/api/servers/'+sid+'/enrollment',{});command=json.loads(data)['command'];self.assertTrue(command.startswith('curl -fsSL '));self.assertTrue(command.endswith(' | bash'))
        url=shlex.split(command)[2];code,script=self.call('/enroll.sh?'+url.split('?',1)[1],auth=False);self.assertEqual(code,200,script)
        text=script.decode();self.assertTrue(text.startswith('#!/usr/bin/env bash\n'));self.assertIn('# Developer: Robo Universal',text);self.assertIn('# Signing status: unsigned;',text)
        embedded=next(line for line in text.splitlines() if line.startswith('printf %s '));source=base64.b64decode(shlex.split(embedded)[2]);self.assertIn(b'DEVELOPER = "Robo Universal"',source);self.assertIn(b'branding is not a verified signature',source)
