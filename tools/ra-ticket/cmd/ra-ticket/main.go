package main

import (
	"context"
	"os"
	"time"

	"romance-agent/tools/ra-ticket/internal/cli"
)

func main() {
	workingDirectory, err := os.Getwd()
	if err != nil {
		_, _ = os.Stderr.WriteString("determine working directory: " + err.Error() + "\n")
		os.Exit(cli.ExitDatabase)
	}
	os.Exit(cli.Run(context.Background(), os.Args[1:], os.Stdout, os.Stderr, cli.Dependencies{
		StartDirectory: workingDirectory,
		Now:            time.Now,
	}))
}
