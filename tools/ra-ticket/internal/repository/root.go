package repository

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

var ErrNotFound = errors.New("repository root not found")

func FindRoot(start string) (string, error) {
	current, err := filepath.Abs(start)
	if err != nil {
		return "", fmt.Errorf("resolve start directory: %w", err)
	}

	for {
		if _, err := os.Stat(filepath.Join(current, ".git")); err == nil {
			return current, nil
		} else if !errors.Is(err, os.ErrNotExist) {
			return "", fmt.Errorf("inspect repository marker: %w", err)
		}

		parent := filepath.Dir(current)
		if parent == current {
			return "", ErrNotFound
		}
		current = parent
	}
}

func DatabasePath(root string) string {
	return filepath.Join(root, ".local", "tickets.db")
}
