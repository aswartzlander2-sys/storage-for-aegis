package main

import (
	"bytes"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
)

func TestSafeKeys(t *testing.T) {
	for _, p := range []string{"", "/etc/passwd", "../outside", "a/../b", "a//b", "a\\b", "C:/outside", "name:stream", "a\x00b", "CON", "NUL.txt", "COM1.csv", "COM¹.csv", "NUL .txt", "LPT9", "CONIN$", "a.", "a ", "x/.ROBO-agent/a", "x/?"} {
		if safeKey(p) == nil {
			t.Errorf("accepted %q", p)
		}
	}
	for _, p := range []string{"docs/file.txt", "日本語/notes.txt", "lptfile.txt", "com10.txt"} {
		if e := safeKey(p); e != nil {
			t.Fatal(p, e)
		}
	}
}
func TestRootedOperations(t *testing.T) {
	path := t.TempDir()
	root, e := os.OpenRoot(path)
	if e != nil {
		t.Fatal(e)
	}
	defer root.Close()
	task := Task{Op: "write", Path: "docs/notes.txt", Data: base64.StdEncoding.EncodeToString([]byte("first"))}
	if _, e = execute(root, path, task); e != nil {
		t.Fatal(e)
	}
	task.Data = base64.StdEncoding.EncodeToString([]byte("second"))
	if _, e = execute(root, path, task); e != nil {
		t.Fatal("replace:", e)
	}
	r, e := execute(root, path, Task{Op: "read", Path: task.Path})
	if e != nil || r["data"] != task.Data {
		t.Fatal(r, e)
	}
	if _, e = execute(root, path, Task{Op: "delete", Path: "docs"}); e == nil {
		t.Fatal("deleted a directory")
	}
	if _, e = execute(root, path, Task{Op: "read", Path: "DOCS/notes.txt"}); e == nil {
		t.Fatal("case alias accepted")
	}
	if _, e = execute(root, path, Task{Op: "write", Path: "docs/notes.txt", Data: "!"}); e == nil {
		t.Fatal("invalid encoding accepted")
	}
	task.Data = base64.StdEncoding.EncodeToString(bytes.Repeat([]byte("x"), maxFile+1))
	if _, e = execute(root, path, task); e == nil {
		t.Fatal("oversized write accepted")
	}
	existing, _ := root.ReadFile(task.Path)
	if string(existing) != "second" {
		t.Fatal("failed write altered original")
	}
	scan, e := execute(root, path, Task{Op: "scan"})
	if e != nil || len(scan["files"].([]map[string]any)) != 1 {
		t.Fatal(scan, e)
	}
	if _, e = execute(root, path, Task{Op: "delete", Path: task.Path}); e != nil {
		t.Fatal(e)
	}
}
func TestNoSymlinkAliases(t *testing.T) {
	path := t.TempDir()
	outside := t.TempDir()
	os.WriteFile(filepath.Join(outside, "secret.txt"), []byte("outside"), 0600)
	os.Mkdir(filepath.Join(path, "private"), 0700)
	os.WriteFile(filepath.Join(path, "private", "secret.txt"), []byte("inside-hidden"), 0600)
	if e := os.Symlink(outside, filepath.Join(path, "external")); e != nil {
		t.Skip(e)
	}
	os.Symlink(filepath.Join(path, "private"), filepath.Join(path, "public-alias"))
	root, e := os.OpenRoot(path)
	if e != nil {
		t.Fatal(e)
	}
	defer root.Close()
	for _, p := range []string{"external/secret.txt", "public-alias/secret.txt"} {
		for _, op := range []string{"read", "write", "delete"} {
			if _, e = execute(root, path, Task{Op: op, Path: p, Data: "eA=="}); e == nil {
				t.Fatal("followed symlink", op, p)
			}
		}
	}
	scan, e := inventory(root, path)
	if e != nil {
		t.Fatal(e)
	}
	files := scan["files"].([]map[string]any)
	if len(files) != 1 || files[0]["path"] != "private/secret.txt" {
		t.Fatal(files)
	}
	content, _ := os.ReadFile(filepath.Join(outside, "secret.txt"))
	if string(content) != "outside" {
		t.Fatal("outside mutated")
	}
}
func TestPayload(t *testing.T) {
	c := Config{URL: "https://checked.example.com", Enrollment: "sensitive-test-only-token", ID: "1234567890abcdef12345678"}
	data, _ := json.Marshal(c)
	var b bytes.Buffer
	b.WriteString("MZplaceholder")
	b.Write(data)
	binary.Write(&b, binary.LittleEndian, uint32(len(data)))
	b.WriteString(trailer)
	path := filepath.Join(t.TempDir(), "test.exe")
	os.WriteFile(path, b.Bytes(), 0600)
	got, e := readPayload(path)
	if e != nil || got.URL != c.URL || got.Enrollment != c.Enrollment || got.ID != c.ID {
		t.Fatal(got, e)
	}
	for _, raw := range [][]byte{[]byte("MZ"), append(b.Bytes(), 1)} {
		os.WriteFile(path, raw, 0600)
		if _, e = readPayload(path); e == nil {
			t.Fatal("corrupt trailer accepted")
		}
	}
}
func TestHTTPSOnly(t *testing.T) {
	for _, s := range []string{"http://host", "https://u:p@host", "https://host?secret=1", "https://host#x", "file:///tmp/x"} {
		if checkURL(s) == nil {
			t.Fatal(s)
		}
	}
	if checkURL("https://host:9443") != nil {
		t.Fatal("valid HTTPS rejected")
	}
}
func TestUsedErrorExact(t *testing.T) {
	want := "This Installer was already used on another system."
	if got := describe(&APIError{Status: 409, Code: "installer_used", Message: "ignored"}); got != want {
		t.Fatal(got)
	}
}

func TestCertificateVerificationAndNoRedirect(t *testing.T) {
	var seen atomic.Int32
	target := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { seen.Add(1); w.Write([]byte(`{}`)) }))
	defer target.Close()
	if _, e := call(Config{URL: target.URL, Token: "test-capability"}, "/agent/poll", map[string]any{}); e == nil {
		t.Fatal("untrusted TLS certificate accepted")
	}
	if seen.Load() != 0 {
		t.Fatal("credential sent before certificate validation")
	}
	source := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Location", target.URL+"/steal")
		w.WriteHeader(302)
		w.Write([]byte(`{"error":"Redirect refused"}`))
	}))
	defer source.Close()
	old := http.DefaultTransport
	http.DefaultTransport = source.Client().Transport
	defer func() { http.DefaultTransport = old }()
	if _, e := call(Config{URL: source.URL, Token: "test-capability"}, "/agent/poll", map[string]any{}); e == nil {
		t.Fatal("redirect accepted")
	}
	if seen.Load() != 0 {
		t.Fatal("credential forwarded across redirect")
	}
}
