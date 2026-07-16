package ticket

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	_ "modernc.org/sqlite"
)

const schema = `
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    summary TEXT NOT NULL CHECK (length(trim(summary)) > 0),
    spec_path TEXT NOT NULL,
    plan_path TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('ready','in_progress','done','cancelled')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    cancelled_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tickets_status_fifo
ON tickets(status, created_at, id);
PRAGMA user_version = 1;
`

type Store struct {
	db   *sql.DB
	root string
	now  func() time.Time
}

func Open(ctx context.Context, root, databasePath string, now func() time.Time) (*Store, error) {
	if now == nil {
		now = time.Now
	}
	absRoot, err := filepath.Abs(root)
	if err != nil {
		return nil, fmt.Errorf("resolve ticket repository root: %w", err)
	}
	root, err = filepath.EvalSymlinks(absRoot)
	if err != nil {
		return nil, fmt.Errorf("resolve ticket repository root: %w", err)
	}
	if err := os.MkdirAll(filepath.Dir(databasePath), 0o755); err != nil {
		return nil, fmt.Errorf("create ticket database directory: %w", err)
	}
	db, err := sql.Open("sqlite", databasePath)
	if err != nil {
		return nil, fmt.Errorf("open ticket database: %w", err)
	}
	db.SetMaxOpenConns(1)
	if _, err := db.ExecContext(ctx, "PRAGMA busy_timeout = 5000"); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("configure ticket database: %w", err)
	}
	var version int
	if err := db.QueryRowContext(ctx, "PRAGMA user_version").Scan(&version); err != nil {
		_ = db.Close()
		return nil, fmt.Errorf("read schema version: %w", err)
	}
	if version > 1 {
		_ = db.Close()
		return nil, fmt.Errorf("unsupported ticket schema version %d", version)
	}
	if version == 0 {
		if _, err := db.ExecContext(ctx, schema); err != nil {
			_ = db.Close()
			return nil, fmt.Errorf("initialize ticket schema: %w", err)
		}
	}
	return &Store{db: db, root: root, now: now}, nil
}

func (s *Store) Close() error { return s.db.Close() }

func (s *Store) Add(ctx context.Context, input CreateInput) (Ticket, error) {
	title := strings.TrimSpace(input.Title)
	summary := strings.TrimSpace(input.Summary)
	spec, err := s.artifactPath(input.SpecPath, filepath.Join("docs", "superpowers", "specs"))
	if err != nil || title == "" || summary == "" {
		return Ticket{}, ErrInvalidArtifact
	}
	plan, err := s.artifactPath(input.PlanPath, filepath.Join("docs", "superpowers", "plans"))
	if err != nil {
		return Ticket{}, ErrInvalidArtifact
	}
	now := s.now().UTC()
	stamp := now.Format(time.RFC3339Nano)
	result, err := s.db.ExecContext(ctx, `
INSERT INTO tickets(title, summary, spec_path, plan_path, status, created_at, updated_at)
VALUES (?, ?, ?, ?, 'ready', ?, ?)`, title, summary, spec, plan, stamp, stamp)
	if err != nil {
		if strings.Contains(err.Error(), "UNIQUE constraint failed: tickets.plan_path") {
			return Ticket{}, ErrDuplicatePlan
		}
		return Ticket{}, fmt.Errorf("insert ticket: %w", err)
	}
	id, err := result.LastInsertId()
	if err != nil {
		return Ticket{}, fmt.Errorf("read ticket id: %w", err)
	}
	return Ticket{ID: id, Title: title, Summary: summary, SpecPath: spec, PlanPath: plan, Status: StatusReady, CreatedAt: now, UpdatedAt: now}, nil
}

func (s *Store) artifactPath(input, requiredDirectory string) (string, error) {
	candidate := input
	if !filepath.IsAbs(candidate) {
		candidate = filepath.Join(s.root, candidate)
	}
	abs, err := filepath.Abs(candidate)
	if err != nil {
		return "", err
	}
	resolved, err := filepath.EvalSymlinks(abs)
	if err != nil {
		return "", err
	}
	rel, err := filepath.Rel(s.root, resolved)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", ErrInvalidArtifact
	}
	required := requiredDirectory + string(filepath.Separator)
	if !strings.HasPrefix(rel, required) || filepath.Ext(rel) != ".md" {
		return "", ErrInvalidArtifact
	}
	info, err := os.Stat(resolved)
	if err != nil || !info.Mode().IsRegular() {
		return "", ErrInvalidArtifact
	}
	return filepath.ToSlash(rel), nil
}

func parseTime(value string) (time.Time, error) {
	return time.Parse(time.RFC3339Nano, value)
}

func parseOptionalTime(value sql.NullString) (*time.Time, error) {
	if !value.Valid {
		return nil, nil
	}
	parsed, err := parseTime(value.String)
	if err != nil {
		return nil, err
	}
	return &parsed, nil
}
