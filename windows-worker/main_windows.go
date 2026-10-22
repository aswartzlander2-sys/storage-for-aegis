//go:build windows

package main

import (
	"bytes"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"unsafe"
)

var kernel32 = syscall.NewLazyDLL("kernel32.dll") // KnownDLL: loader-owned system library.
// Load all other native libraries from System32, never the Downloads/current folder.
func systemDLL(name string) *syscall.LazyDLL {
	path := make([]uint16, 32768)
	n, _, _ := kernel32.NewProc("GetSystemDirectoryW").Call(uintptr(unsafe.Pointer(&path[0])), uintptr(len(path)))
	if n == 0 || n >= uintptr(len(path)) {
		panic("Cannot locate Windows system libraries")
	}
	return syscall.NewLazyDLL(filepath.Join(syscall.UTF16ToString(path[:n]), name))
}

var user32 = systemDLL("user32.dll")
var shell32 = systemDLL("shell32.dll")
var ole32 = systemDLL("ole32.dll")
var crypt32 = systemDLL("crypt32.dll")
var advapi = systemDLL("advapi32.dll")

func appInstance() uintptr { h, _, _ := kernel32.NewProc("GetModuleHandleW").Call(0); return h }
func setWindowIcons(hwnd uintptr) {
	for _, size := range []struct{ kind, px uintptr }{{0, 16}, {1, 32}} {
		icon, _, _ := user32.NewProc("LoadImageW").Call(appInstance(), uintptr(unsafe.Pointer(wide("APP"))), 1, size.px, size.px, 0x8000)
		if icon != 0 {
			user32.NewProc("SendMessageW").Call(hwnd, 0x80, size.kind, icon)
		}
	}
}

var folderIconCallback = syscall.NewCallback(func(hwnd, msg, param, data uintptr) uintptr {
	if msg == 1 {
		user32.NewProc("SetWindowTextW").Call(hwnd, uintptr(unsafe.Pointer(wide(appName))))
		setWindowIcons(hwnd)
	}
	return 0
})

var messageIconCallback = syscall.NewCallback(func(code, w, l uintptr) uintptr {
	if code == 5 {
		setWindowIcons(w)
	}
	r, _, _ := user32.NewProc("CallNextHookEx").Call(0, code, w, l)
	return r
})

func wide(s string) *uint16 { p, _ := syscall.UTF16PtrFromString(s); return p }
func message(s string, isError bool) {
	flags := uintptr(0x40)
	if isError {
		flags = 0x10
	}
	// Keep standard Windows error/info content and buttons, but brand the title/taskbar icon.
	thread, _, _ := kernel32.NewProc("GetCurrentThreadId").Call()
	hook, _, _ := user32.NewProc("SetWindowsHookExW").Call(5, messageIconCallback, 0, thread)
	if hook != 0 {
		defer user32.NewProc("UnhookWindowsHookEx").Call(hook)
	}
	user32.NewProc("MessageBoxW").Call(0, uintptr(unsafe.Pointer(wide(s))), uintptr(unsafe.Pointer(wide(appName))), flags)
}

// A standard Win32 dialog with ordinary Windows push buttons; no HTML/custom skin.
func confirmInstall() bool {
	var b bytes.Buffer
	put := func(v any) { binary.Write(&b, binary.LittleEndian, v) }
	str := func(s string) {
		u, _ := syscall.UTF16FromString(s)
		for _, v := range u {
			put(v)
		}
	}
	align := func() {
		for b.Len()%4 != 0 {
			b.WriteByte(0)
		}
	}
	put(uint32(0x80c808c0))
	put(uint32(0))
	put(uint16(4))
	put(int16(0))
	put(int16(0))
	put(int16(280))
	put(int16(110))
	put(uint16(0))
	put(uint16(0))
	str(appName)
	put(uint16(9))
	str("Segoe UI")
	control := func(style uint32, x, y, cx, cy int16, id, cls uint16, text string) {
		align()
		put(style)
		put(uint32(0))
		put(x)
		put(y)
		put(cx)
		put(cy)
		put(id)
		put(uint16(0xffff))
		put(cls)
		str(text)
		put(uint16(0))
	}
	control(0x50000003, 12, 12, 24, 24, 101, 0x82, "APP")
	control(0x50000000, 44, 12, 224, 60, 100, 0x82, "Install Robo Cloud Enrollment on this PC?\r\n\r\nIt connects only the folder you choose and starts at your Windows sign-in. Cancel makes no installation changes.")
	control(0x50010000, 122, 82, 70, 17, 2, 0x80, "Cancel")
	control(0x50010001, 198, 82, 70, 17, 1, 0x80, "Continue")
	callback := syscall.NewCallback(func(hwnd, msg, w, l uintptr) uintptr {
		if msg == 0x110 {
			setWindowIcons(hwnd)
			return 1
		}
		if msg == 0x10 {
			user32.NewProc("EndDialog").Call(hwnd, 2)
			return 1
		}
		if msg == 0x111 {
			if id := w & 0xffff; id == 1 || id == 2 {
				user32.NewProc("EndDialog").Call(hwnd, id)
				return 1
			}
		}
		return 0
	})
	data := b.Bytes()
	r, _, _ := user32.NewProc("DialogBoxIndirectParamW").Call(appInstance(), uintptr(unsafe.Pointer(&data[0])), 0, callback, 0)
	return r == 1
}

type browseInfo struct {
	Owner    uintptr
	Root     uintptr
	Display  *uint16
	Title    *uint16
	Flags    uint32
	Callback uintptr
	Param    uintptr
	Image    int32
}

func chooseFolder() (string, error) {
	ole32.NewProc("OleInitialize").Call(0)
	defer ole32.NewProc("OleUninitialize").Call()
	display := make([]uint16, 260)
	bi := browseInfo{Display: &display[0], Title: wide("Robo Cloud Enrollment — choose a storage folder"), Flags: 0x51, Callback: folderIconCallback}
	id, _, _ := shell32.NewProc("SHBrowseForFolderW").Call(uintptr(unsafe.Pointer(&bi)))
	if id == 0 {
		return "", nil
	}
	defer ole32.NewProc("CoTaskMemFree").Call(id)
	path := make([]uint16, 260)
	ok, _, _ := shell32.NewProc("SHGetPathFromIDListW").Call(id, uintptr(unsafe.Pointer(&path[0])))
	if ok == 0 {
		return "", errors.New("Choose a local filesystem folder")
	}
	return syscall.UTF16ToString(path), nil
}
func safeRoot(path string) error {
	path = filepath.Clean(path)
	vol := filepath.VolumeName(path)
	if len(vol) != 2 || vol[1] != ':' || !filepath.IsAbs(path) || path == vol+"\\" || strings.HasPrefix(path, "\\\\") {
		return errors.New("Choose a local folder, not a drive root or network share")
	}
	for p := path; ; p = filepath.Dir(p) {
		attrs, e := syscall.GetFileAttributes(wide(p))
		if e != nil {
			return errors.New("The chosen folder is unavailable")
		}
		if attrs&0x400 != 0 {
			return errors.New("The storage folder and its parents cannot be junctions or symbolic links")
		}
		if p == filepath.Dir(p) {
			break
		}
	}
	return nil
}
func diskSpace(path string) (int64, int64, error) {
	var free, total, all uint64
	r, _, e := kernel32.NewProc("GetDiskFreeSpaceExW").Call(uintptr(unsafe.Pointer(wide(path))), uintptr(unsafe.Pointer(&free)), uintptr(unsafe.Pointer(&total)), uintptr(unsafe.Pointer(&all)))
	if r == 0 {
		return 0, 0, e
	}
	return int64(total), int64(free), nil
}

type blob struct {
	Size uint32
	Data *byte
}

func protect(data []byte, decrypt bool) ([]byte, error) {
	if len(data) == 0 {
		return nil, errors.New("Empty credential")
	}
	input := blob{uint32(len(data)), &data[0]}
	var out blob
	var ok uintptr
	var e error
	if decrypt {
		ok, _, e = crypt32.NewProc("CryptUnprotectData").Call(uintptr(unsafe.Pointer(&input)), 0, 0, 0, 0, 1, uintptr(unsafe.Pointer(&out)))
	} else {
		ok, _, e = crypt32.NewProc("CryptProtectData").Call(uintptr(unsafe.Pointer(&input)), 0, 0, 0, 0, 1, uintptr(unsafe.Pointer(&out)))
	}
	if ok == 0 {
		return nil, e
	}
	defer kernel32.NewProc("LocalFree").Call(uintptr(unsafe.Pointer(out.Data)))
	return append([]byte(nil), unsafe.Slice(out.Data, out.Size)...), nil
}
func autorun(id, command string, remove bool) error {
	var h uintptr
	name := wide("Software\\Microsoft\\Windows\\CurrentVersion\\Run")
	r, _, _ := advapi.NewProc("RegCreateKeyExW").Call(0x80000001, uintptr(unsafe.Pointer(name)), 0, 0, 0, 0x0002, 0, uintptr(unsafe.Pointer(&h)), 0)
	if r != 0 {
		return errors.New("Cannot configure per-user startup")
	}
	defer advapi.NewProc("RegCloseKey").Call(h)
	key := wide("RoboCloud-" + id)
	if remove {
		advapi.NewProc("RegDeleteValueW").Call(h, uintptr(unsafe.Pointer(key)))
		return nil
	}
	value, _ := syscall.UTF16FromString(command)
	r, _, _ = advapi.NewProc("RegSetValueExW").Call(h, uintptr(unsafe.Pointer(key)), 0, 1, uintptr(unsafe.Pointer(&value[0])), uintptr(len(value)*2))
	if r != 0 {
		return errors.New("Cannot save per-user startup")
	}
	return nil
}
func removeAutorun(id string) { autorun(id, "", true) }
func saveConfig(path string, c Config) error {
	secret, e := protect([]byte(c.Token), false)
	if e != nil {
		return e
	}
	c.Token = ""
	c.Enrollment = ""
	c.Protected = secret
	data, e := json.Marshal(c)
	if e != nil {
		return e
	}
	return os.WriteFile(path, data, 0600)
}
func loadConfig(path string) (Config, error) {
	var c Config
	d, e := os.ReadFile(path)
	if e != nil {
		return c, e
	}
	if e = json.Unmarshal(d, &c); e != nil {
		return c, e
	}
	token, e := protect(c.Protected, true)
	c.Token = string(token)
	return c, e
}
func install(c Config, source string) error {
	rootPath, e := chooseFolder()
	if e != nil || rootPath == "" {
		return e
	}
	if e = storageRoot(rootPath); e != nil {
		return e
	}
	rootPath, e = canonicalFolder(rootPath)
	if e != nil {
		return e
	}
	root, e := os.OpenRoot(rootPath)
	if e != nil {
		return e
	}
	defer root.Close()
	probe := ".robo-probe-" + randomID()
	defer root.Remove(probe)
	f, e := root.OpenFile(probe, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if e != nil {
		return errors.New("The selected folder is not writable")
	}
	_, e = f.Write([]byte("Robo Cloud Windows probe"))
	if e == nil {
		e = f.Sync()
	}
	f.Close()
	if e != nil {
		return e
	}
	read, e := root.ReadFile(probe)
	if e != nil || string(read) != "Robo Cloud Windows probe" {
		return errors.New("Folder read-back probe failed")
	}
	if e = root.Remove(probe); e != nil {
		return e
	}
	info, e := inventory(root, rootPath)
	if e != nil {
		return errors.New("Folder inventory failed; no installation was made")
	}
	host, _ := os.Hostname()
	info["root"] = rootPath
	info["hostname"] = host
	info["platform"] = "windows"
	info["device"] = c.ID
	app, e := os.UserCacheDir()
	if e != nil {
		return e
	}
	home := filepath.Join(app, "RoboCloud", "workers", c.ID)
	if e = safeRoot(app); e != nil {
		return e
	}
	base, e := os.OpenRoot(app)
	if e != nil {
		return e
	}
	defer base.Close()
	if e = base.MkdirAll(filepath.Join("RoboCloud", "workers", c.ID), 0700); e != nil {
		return e
	}
	if e = safeRoot(home); e != nil {
		return e
	}
	exe := filepath.Join(home, "Robo Cloud Enrollment.exe")
	in, e := os.Open(source)
	if e != nil {
		return e
	}
	defer in.Close()
	out, e := os.OpenFile(exe, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0700)
	if e != nil {
		return errors.New("An installation with this identity already exists")
	}
	_, e = io.Copy(out, in)
	out.Close()
	if e != nil {
		return e
	}
	response, e := call(c, "/agent/enroll", info)
	if e != nil {
		os.Remove(exe)
		return e
	}
	if json.Unmarshal(response["token"], &c.Token) != nil || c.Token == "" {
		return errors.New("Missing worker credential; generate a fresh installer")
	}
	c.Enrollment = ""
	c.Root = rootPath
	config := filepath.Join(home, "config.json")
	if e = saveConfig(config, c); e != nil {
		return errors.New("Cannot protect the worker credential. Generate a fresh installer")
	}
	command := syscall.EscapeArg(exe) + " --worker " + syscall.EscapeArg(config)
	if e = autorun(c.ID, command, false); e != nil {
		return e
	}
	cmd := exec.Command(exe, "--worker", config)
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
	if e = cmd.Start(); e != nil {
		removeAutorun(c.ID)
		return errors.New("The worker could not start; generate a fresh installer")
	}
	cmd.Process.Release()
	message("Robo Cloud Enrollment is installed. The folder worker starts at your Windows sign-in. Aegis will show Verified after its first heartbeat.", false)
	return nil
}
func main() {
	runtime.LockOSThread()
	if len(os.Args) == 3 && os.Args[1] == "--worker" {
		c, e := loadConfig(os.Args[2])
		if e == nil {
			runWorker(c)
		}
		return
	}
	source, e := os.Executable()
	if e != nil {
		message("Cannot locate this installer", true)
		return
	}
	c, e := readPayload(source)
	if e != nil {
		message(describe(e), true)
		return
	}
	if _, e = call(c, "/agent/installer/check", map[string]any{"platform": "windows"}); e != nil {
		message(describe(e), true)
		return
	}
	if !confirmInstall() {
		return
	}
	if e = install(c, source); e != nil {
		message(describe(e), true)
	}
}

func isReparse(info fs.FileInfo) bool {
	if info.Mode()&os.ModeSymlink != 0 {
		return true
	}
	if data, ok := info.Sys().(*syscall.Win32FileAttributeData); ok {
		return data.FileAttributes&0x400 != 0
	}
	return false
}
func validateWorkerRoot(path string) error { return storageRoot(path) }

// Resolve the DOS-volume long path by handle, including 8.3 aliases and spelling.
func canonicalFolder(path string) (string, error) {
	f, e := os.Open(path)
	if e != nil {
		return "", e
	}
	defer f.Close()
	buffer := make([]uint16, 32768)
	n, _, e := kernel32.NewProc("GetFinalPathNameByHandleW").Call(f.Fd(), uintptr(unsafe.Pointer(&buffer[0])), uintptr(len(buffer)), 0)
	if n == 0 || n >= uintptr(len(buffer)) {
		return "", e
	}
	value := syscall.UTF16ToString(buffer[:n])
	value = strings.TrimPrefix(value, `\\?\`)
	return value, nil
}

// Storage must never expose the worker's own executable/configuration or system trees.
func storageRoot(path string) error {
	if e := safeRoot(path); e != nil {
		return e
	}
	normalized := func(p string) string { return strings.ToLower(strings.TrimRight(filepath.Clean(p), "\\/")) }
	within := func(parent, child string) bool { return child == parent || strings.HasPrefix(child, parent+"\\") }
	actual, e := canonicalFolder(path)
	if e != nil {
		return e
	}
	selected := normalized(actual)
	cache, e := os.UserCacheDir()
	if e != nil {
		return e
	}
	cache, e = canonicalFolder(cache)
	if e != nil {
		return e
	}
	installation := normalized(filepath.Join(cache, "RoboCloud"))
	if within(selected, installation) || within(installation, selected) {
		return errors.New("Choose a dedicated storage folder, not your profile, AppData or the worker installation folder")
	}
	for _, env := range []string{"SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"} {
		if system := os.Getenv(env); system != "" {
			actual, e := canonicalFolder(system)
			if e != nil {
				return e
			}
			if within(normalized(actual), selected) {
				return errors.New("System and program folders cannot be storage roots")
			}
		}
	}
	return nil
}
