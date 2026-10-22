package main

import (
	"bytes"
	"crypto/rand"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

const appName = "Robo Cloud Enrollment"

const maxFile = 16 * 1024 * 1024
const trailer = "ROBOCLOUD-ENROLL-V1"

type Config struct {
	URL        string `json:"url"`
	Enrollment string `json:"enrollment,omitempty"`
	Token      string `json:"token,omitempty"`
	Root       string `json:"root"`
	ID         string `json:"id"`
	Protected  []byte `json:"protected,omitempty"`
}
type Task struct {
	ID   string `json:"id"`
	Op   string `json:"op"`
	Path string `json:"path"`
	Data string `json:"data"`
}
type APIError struct {
	Status  int
	Message string
	Code    string
}

func (e *APIError) Error() string { return e.Message }
func client() *http.Client {
	return &http.Client{Timeout: 80 * time.Second, CheckRedirect: func(_ *http.Request, _ []*http.Request) error { return http.ErrUseLastResponse }}
}
func checkURL(s string) error {
	u, e := url.Parse(s)
	if e != nil || u.Scheme != "https" || u.Hostname() == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
		return errors.New("A certificate-verified HTTPS callback is required")
	}
	return nil
}
func call(c Config, path string, body any) (map[string]json.RawMessage, error) {
	if e := checkURL(c.URL); e != nil {
		return nil, e
	}
	data, e := json.Marshal(body)
	if e != nil {
		return nil, e
	}
	req, e := http.NewRequest("POST", strings.TrimRight(c.URL, "/")+path, bytes.NewReader(data))
	if e != nil {
		return nil, e
	}
	req.Header.Set("Content-Type", "application/json")
	token := c.Token
	if token == "" {
		token = c.Enrollment
	}
	req.Header.Set("Authorization", "Bearer "+token)
	r, e := client().Do(req)
	if e != nil {
		return nil, errors.New("Cannot reach the verified HTTPS storage gateway")
	}
	defer r.Body.Close()
	raw, e := io.ReadAll(io.LimitReader(r.Body, 48*1024*1024+1))
	if e != nil || len(raw) > 48*1024*1024 {
		return nil, errors.New("Gateway response exceeded its limit")
	}
	var out map[string]json.RawMessage
	if e = json.Unmarshal(raw, &out); e != nil {
		return nil, errors.New("Invalid gateway response")
	}
	if r.StatusCode != 200 {
		var msg, code string
		json.Unmarshal(out["error"], &msg)
		json.Unmarshal(out["code"], &code)
		if msg == "" {
			msg = "Storage gateway refused this operation"
		}
		return nil, &APIError{r.StatusCode, msg, code}
	}
	return out, nil
}
func randomID() string {
	b := make([]byte, 16)
	if _, e := rand.Read(b); e != nil {
		panic(e)
	}
	return hex.EncodeToString(b)
}

// Windows path aliases (ADS, device names, trailing dots/spaces) must not bypass gateway keys.
func safeKey(p string) error {
	if p == "" || len(p) > 1024 || strings.ContainsAny(p, "\\:\x00") || strings.HasPrefix(p, "/") {
		return errors.New("Unsafe relative path")
	}
	for _, s := range strings.Split(p, "/") {
		if s == "" || s == "." || s == ".." || strings.EqualFold(s, ".robo-agent") || strings.TrimRight(s, ". ") != s || strings.ContainsAny(s, "<>\"|?*") {
			return errors.New("Unsafe path component")
		}
		for _, c := range s {
			if c < 32 {
				return errors.New("Unsafe path character")
			}
		}
		base := strings.ToUpper(strings.TrimRight(strings.SplitN(s, ".", 2)[0], " ."))
		base = strings.NewReplacer("¹", "1", "²", "2", "³", "3").Replace(base)
		if base == "CON" || base == "PRN" || base == "AUX" || base == "NUL" || base == "CLOCK$" || base == "CONIN$" || base == "CONOUT$" || (len(base) == 4 && (strings.HasPrefix(base, "COM") || strings.HasPrefix(base, "LPT")) && base[3] >= '1' && base[3] <= '9') {
			return errors.New("Reserved Windows filename")
		}
	}
	return nil
}

// Require exact directory entry spelling; reject NTFS case and 8.3 aliases so
// case-sensitive gateway ACLs cannot be bypassed by alternate Windows names.
func canonical(root *os.Root, p string, create bool) error {
	parent := "."
	for _, name := range strings.Split(p, "/") {
		dir, e := root.Open(parent)
		if e != nil {
			return e
		}
		entries, e := dir.ReadDir(-1)
		dir.Close()
		if e != nil {
			return e
		}
		exact := false
		for _, entry := range entries {
			if entry.Name() == name {
				exact = true
				break
			}
		}
		next := filepath.Join(parent, name)
		if !exact {
			_, e := root.Lstat(next)
			if e == nil {
				return errors.New("Use the exact storage path, not a filesystem alias")
			}
			if create && os.IsNotExist(e) {
				return nil
			}
			return errors.New("Storage path not found")
		}
		info, e := root.Lstat(next)
		if e != nil {
			return e
		}
		if isReparse(info) {
			return errors.New("Reparse points and symbolic links are not storage paths")
		}
		parent = next
	}
	return nil
}
func inventory(root *os.Root, rootPath string) (map[string]any, error) {
	out := []map[string]any{}
	e := fs.WalkDir(root.FS(), ".", func(p string, d fs.DirEntry, e error) error {
		if e != nil {
			return e
		}
		if p == "." {
			return nil
		}
		if strings.EqualFold(d.Name(), ".robo-agent") {
			if d.IsDir() {
				return fs.SkipDir
			}
			return nil
		}
		if d.Type()&os.ModeSymlink != 0 {
			if d.IsDir() {
				return fs.SkipDir
			}
			return nil
		}
		if e = safeKey(p); e != nil {
			return e
		}
		info, e := d.Info()
		if e != nil {
			return e
		}
		if isReparse(info) {
			if d.IsDir() {
				return fs.SkipDir
			}
			return nil
		}
		if d.IsDir() {
			return nil
		}
		if !info.Mode().IsRegular() {
			return nil
		}
		out = append(out, map[string]any{"path": p, "size": info.Size()})
		if len(out) > 100000 {
			return errors.New("Inventory exceeds 100,000 files")
		}
		return nil
	})
	if e != nil {
		return nil, e
	}
	total, free, e := diskSpace(rootPath)
	return map[string]any{"files": out, "capacity": total, "free": free}, e
}
func execute(root *os.Root, rootPath string, t Task) (map[string]any, error) {
	if t.Op == "scan" {
		return inventory(root, rootPath)
	}
	if e := safeKey(t.Path); e != nil {
		return nil, e
	}
	if e := canonical(root, t.Path, t.Op == "write"); e != nil {
		return nil, e
	}
	switch t.Op {
	case "read":
		f, e := root.Open(filepath.FromSlash(t.Path))
		if e != nil {
			return nil, e
		}
		defer f.Close()
		info, e := f.Stat()
		if e != nil || !info.Mode().IsRegular() {
			return nil, errors.New("Not a regular file")
		}
		data, e := io.ReadAll(io.LimitReader(f, maxFile+1))
		if e != nil || len(data) > maxFile {
			return nil, errors.New("Read exceeds 16 MiB")
		}
		return map[string]any{"data": base64.StdEncoding.EncodeToString(data)}, nil
	case "write":
		data, e := base64.StdEncoding.Strict().DecodeString(t.Data)
		if e != nil || len(data) > maxFile {
			return nil, errors.New("Invalid or oversized write")
		}
		_, free, e := diskSpace(rootPath)
		if e != nil || free < int64(len(data))+1024*1024 {
			return nil, errors.New("Insufficient free space")
		}
		name := filepath.FromSlash(t.Path)
		parent := filepath.Dir(name)
		if parent != "." {
			if e = root.MkdirAll(parent, 0700); e != nil {
				return nil, e
			}
		}
		tmp := filepath.Join(parent, ".robo-write-"+randomID())
		f, e := root.OpenFile(tmp, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if e != nil {
			return nil, e
		}
		defer root.Remove(tmp)
		_, e = f.Write(data)
		if e == nil {
			e = f.Sync()
		}
		ce := f.Close()
		if e != nil {
			return nil, e
		}
		if ce != nil {
			return nil, ce
		}
		if e = root.Rename(tmp, name); e != nil {
			return nil, e
		}
		verify, e := root.ReadFile(name)
		if e != nil || !bytes.Equal(verify, data) {
			return nil, errors.New("Write verification failed")
		}
		return map[string]any{"ok": true}, nil
	case "delete":
		info, e := root.Stat(filepath.FromSlash(t.Path))
		if e != nil {
			return nil, e
		}
		if !info.Mode().IsRegular() {
			return nil, errors.New("Only regular files can be deleted")
		}
		if e = root.Remove(filepath.FromSlash(t.Path)); e != nil {
			return nil, e
		}
		return map[string]any{"ok": true}, nil
	}
	return nil, errors.New("Unknown storage operation")
}
func readPayload(path string) (Config, error) {
	var c Config
	f, e := os.Open(path)
	if e != nil {
		return c, e
	}
	defer f.Close()
	st, e := f.Stat()
	if e != nil {
		return c, e
	}
	n := len(trailer) + 4
	if st.Size() < int64(n) {
		return c, errors.New("Download a fresh installer from Aegis")
	}
	tail := make([]byte, n)
	if _, e = f.ReadAt(tail, st.Size()-int64(n)); e != nil {
		return c, e
	}
	if string(tail[4:]) != trailer {
		return c, errors.New("Download a personalized installer from Aegis")
	}
	size := int64(binary.LittleEndian.Uint32(tail[:4]))
	if size < 1 || size > 16384 || size+int64(n) > st.Size() {
		return c, errors.New("Invalid installer configuration")
	}
	data := make([]byte, size)
	if _, e = f.ReadAt(data, st.Size()-int64(n)-size); e != nil {
		return c, e
	}
	if e = json.Unmarshal(data, &c); e != nil {
		return c, e
	}
	if e = checkURL(c.URL); e != nil {
		return c, e
	}
	if c.Enrollment == "" || !regexp.MustCompile(`^[a-f0-9]{16,64}$`).MatchString(c.ID) {
		return c, errors.New("Missing enrollment capability")
	}
	return c, nil
}
func runWorker(c Config) {
	if validateWorkerRoot(c.Root) != nil {
		return
	}
	if checkURL(c.URL) != nil || c.Token == "" {
		return
	}
	root, e := os.OpenRoot(c.Root)
	if e != nil {
		return
	}
	defer root.Close()
	for {
		response, e := call(c, "/agent/poll", map[string]any{})
		if e != nil {
			var api *APIError
			if errors.As(e, &api) && (api.Status == 401 || api.Status == 403 || api.Status == 410) {
				removeAutorun(c.ID)
				return
			}
			time.Sleep(5 * time.Second)
			continue
		}
		var t Task
		if json.Unmarshal(response["task"], &t) != nil || t.ID == "" {
			time.Sleep(2 * time.Second)
			continue
		}
		result, e := execute(root, c.Root, t)
		if e != nil {
			result = map[string]any{"error": "Windows storage operation failed. Check the chosen folder and permissions."}
		}
		call(c, "/agent/result", map[string]any{"task": t.ID, "result": result})
	}
}
func usedError(e error) bool { var a *APIError; return errors.As(e, &a) && a.Code == "installer_used" }
func describe(e error) string {
	if usedError(e) {
		return "This Installer was already used on another system."
	}
	return fmt.Sprint(e)
}
