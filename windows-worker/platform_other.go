//go:build !windows

package main

import (
	"fmt"
	"io/fs"
	"os"
	"syscall"
)

func diskSpace(path string) (int64, int64, error) {
	var s syscall.Statfs_t
	e := syscall.Statfs(path, &s)
	return int64(s.Blocks) * int64(s.Bsize), int64(s.Bavail) * int64(s.Bsize), e
}
func removeAutorun(id string) {}
func main() {
	fmt.Println("The installer requires Windows 10/11 x64. This build is for portable worker tests only.")
}

func isReparse(info fs.FileInfo) bool      { return info.Mode()&os.ModeSymlink != 0 }
func validateWorkerRoot(path string) error { _, e := os.Stat(path); return e }
