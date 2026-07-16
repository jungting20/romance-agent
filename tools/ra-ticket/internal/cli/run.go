package cli

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"strconv"
	"strings"
	"time"

	"romance-agent/tools/ra-ticket/internal/repository"
	"romance-agent/tools/ra-ticket/internal/ticket"
)

type Dependencies struct {
	StartDirectory string
	Now            func() time.Time
}

const (
	ExitOK                = 0
	ExitDatabase          = 1
	ExitUsage             = 2
	ExitNotFound          = 3
	ExitInvalidTransition = 4
	ExitDuplicate         = 5
	ExitEmptyQueue        = 6
	ExitValidation        = 7
)

type errorOutput struct {
	Error string `json:"error"`
	Code  string `json:"code"`
}

func Run(ctx context.Context, args []string, stdout, stderr io.Writer, dependencies Dependencies) int {
	root, err := repository.FindRoot(dependencies.StartDirectory)
	if err != nil {
		return reportError(stderr, hasJSON(args), err)
	}
	store, err := ticket.Open(ctx, root, repository.DatabasePath(root), dependencies.Now)
	if err != nil {
		return reportError(stderr, hasJSON(args), err)
	}
	defer store.Close()

	if len(args) == 0 {
		return reportUsage(stderr, false, "missing command")
	}

	switch args[0] {
	case "add":
		return runAdd(ctx, store, args[1:], stdout, stderr)
	case "list":
		return runList(ctx, store, args[1:], stdout, stderr)
	case "next":
		return runNext(ctx, store, args[1:], stdout, stderr)
	case "show":
		return runShow(ctx, store, args[1:], stdout, stderr)
	case "start":
		return runTransition(ctx, store, ticket.ActionStart, args[1:], stdout, stderr)
	case "done":
		return runTransition(ctx, store, ticket.ActionDone, args[1:], stdout, stderr)
	case "cancel":
		return runTransition(ctx, store, ticket.ActionCancel, args[1:], stdout, stderr)
	case "reopen":
		return runTransition(ctx, store, ticket.ActionReopen, args[1:], stdout, stderr)
	default:
		return reportUsage(stderr, hasJSON(args), "unknown command: "+args[0])
	}
}

func runAdd(ctx context.Context, store *ticket.Store, args []string, stdout, stderr io.Writer) int {
	flags := newFlagSet("add")
	title := flags.String("title", "", "ticket title")
	summary := flags.String("summary", "", "ticket summary")
	spec := flags.String("spec", "", "approved design path")
	plan := flags.String("plan", "", "approved implementation plan path")
	jsonOutput := flags.Bool("json", false, "write JSON")
	if err := flags.Parse(args); err != nil {
		return reportUsage(stderr, hasJSON(args), err.Error())
	}
	if len(flags.Args()) != 0 {
		return reportUsage(stderr, *jsonOutput, "add does not accept positional arguments")
	}
	if !visited(flags, "title") || !visited(flags, "summary") || !visited(flags, "spec") || !visited(flags, "plan") {
		return reportUsage(stderr, *jsonOutput, "add requires --title, --summary, --spec, and --plan")
	}
	created, err := store.Add(ctx, ticket.CreateInput{
		Title:    *title,
		Summary:  *summary,
		SpecPath: *spec,
		PlanPath: *plan,
	})
	if err != nil {
		return reportError(stderr, *jsonOutput, err)
	}
	return reportTicket(stdout, *jsonOutput, created)
}

func runList(ctx context.Context, store *ticket.Store, args []string, stdout, stderr io.Writer) int {
	flags := newFlagSet("list")
	status := flags.String("status", "", "filter by ticket status")
	jsonOutput := flags.Bool("json", false, "write JSON")
	if err := flags.Parse(args); err != nil {
		return reportUsage(stderr, hasJSON(args), err.Error())
	}
	if len(flags.Args()) != 0 {
		return reportUsage(stderr, *jsonOutput, "list does not accept positional arguments")
	}
	var filter *ticket.Status
	if visited(flags, "status") {
		parsed := ticket.Status(*status)
		filter = &parsed
	}
	tickets, err := store.List(ctx, filter)
	if err != nil {
		return reportError(stderr, *jsonOutput, err)
	}
	return reportTickets(stdout, *jsonOutput, tickets)
}

func runNext(ctx context.Context, store *ticket.Store, args []string, stdout, stderr io.Writer) int {
	flags := newFlagSet("next")
	jsonOutput := flags.Bool("json", false, "write JSON")
	if err := flags.Parse(args); err != nil {
		return reportUsage(stderr, hasJSON(args), err.Error())
	}
	if len(flags.Args()) != 0 {
		return reportUsage(stderr, *jsonOutput, "next does not accept positional arguments")
	}
	next, err := store.Next(ctx)
	if err != nil {
		return reportError(stderr, *jsonOutput, err)
	}
	return reportTicket(stdout, *jsonOutput, next)
}

func runShow(ctx context.Context, store *ticket.Store, args []string, stdout, stderr io.Writer) int {
	id, jsonOutput, err := parseIDArgs("show", args)
	if err != nil {
		return reportUsage(stderr, hasJSON(args), err.Error())
	}
	found, err := store.Get(ctx, id)
	if err != nil {
		return reportError(stderr, jsonOutput, err)
	}
	return reportTicket(stdout, jsonOutput, found)
}

func runTransition(ctx context.Context, store *ticket.Store, action ticket.Action, args []string, stdout, stderr io.Writer) int {
	id, jsonOutput, err := parseIDArgs(string(action), args)
	if err != nil {
		return reportUsage(stderr, hasJSON(args), err.Error())
	}
	updated, err := store.Transition(ctx, id, action)
	if err != nil {
		return reportError(stderr, jsonOutput, err)
	}
	return reportTicket(stdout, jsonOutput, updated)
}

func parseIDArgs(command string, args []string) (int64, bool, error) {
	flags := newFlagSet(command)
	jsonOutput := flags.Bool("json", false, "write JSON")
	flagArgs, positional := splitFlags(args)
	if err := flags.Parse(flagArgs); err != nil {
		return 0, false, err
	}
	if len(positional) != 1 {
		return 0, *jsonOutput, fmt.Errorf("%s requires one positive integer ID", command)
	}
	id, err := strconv.ParseInt(positional[0], 10, 64)
	if err != nil || id <= 0 {
		return 0, *jsonOutput, fmt.Errorf("%s requires one positive base-10 integer ID", command)
	}
	return id, *jsonOutput, nil
}

func splitFlags(args []string) ([]string, []string) {
	flags := make([]string, 0, len(args))
	positionals := make([]string, 0, 1)
	for _, arg := range args {
		if strings.HasPrefix(arg, "-") {
			flags = append(flags, arg)
		} else {
			positionals = append(positionals, arg)
		}
	}
	return flags, positionals
}

func newFlagSet(name string) *flag.FlagSet {
	flags := flag.NewFlagSet(name, flag.ContinueOnError)
	flags.SetOutput(io.Discard)
	return flags
}

func visited(flags *flag.FlagSet, name string) bool {
	found := false
	flags.Visit(func(current *flag.Flag) {
		if current.Name == name {
			found = true
		}
	})
	return found
}

func reportTicket(stdout io.Writer, jsonOutput bool, value ticket.Ticket) int {
	if jsonOutput {
		if err := json.NewEncoder(stdout).Encode(value); err != nil {
			return ExitDatabase
		}
		return ExitOK
	}
	_, _ = fmt.Fprintf(stdout, "ID: %d\nStatus: %s\nTitle: %s\nSummary: %s\nSpec: %s\nPlan: %s\n", value.ID, value.Status, value.Title, value.Summary, value.SpecPath, value.PlanPath)
	return ExitOK
}

func reportTickets(stdout io.Writer, jsonOutput bool, values []ticket.Ticket) int {
	if jsonOutput {
		if err := json.NewEncoder(stdout).Encode(values); err != nil {
			return ExitDatabase
		}
		return ExitOK
	}
	if len(values) == 0 {
		_, _ = fmt.Fprintln(stdout, "No tickets.")
		return ExitOK
	}
	for _, value := range values {
		_, _ = fmt.Fprintf(stdout, "%d\t%s\t%s\t%s\n", value.ID, value.Status, value.Title, value.PlanPath)
	}
	return ExitOK
}

func reportUsage(stderr io.Writer, jsonOutput bool, message string) int {
	if jsonOutput {
		_ = json.NewEncoder(stderr).Encode(errorOutput{Error: message, Code: "usage"})
	} else {
		_, _ = fmt.Fprintln(stderr, message)
	}
	return ExitUsage
}

func reportError(stderr io.Writer, jsonOutput bool, err error) int {
	exitCode, errorCode := classifyError(err)
	if jsonOutput {
		_ = json.NewEncoder(stderr).Encode(errorOutput{Error: err.Error(), Code: errorCode})
	} else {
		_, _ = fmt.Fprintln(stderr, err)
	}
	return exitCode
}

func classifyError(err error) (int, string) {
	switch {
	case errors.Is(err, ticket.ErrNotFound):
		return ExitNotFound, "not_found"
	case errors.Is(err, ticket.ErrInvalidTransition):
		return ExitInvalidTransition, "invalid_transition"
	case errors.Is(err, ticket.ErrDuplicatePlan):
		return ExitDuplicate, "duplicate"
	case errors.Is(err, ticket.ErrEmptyQueue):
		return ExitEmptyQueue, "empty_queue"
	case errors.Is(err, ticket.ErrInvalidArtifact), errors.Is(err, repository.ErrNotFound):
		return ExitValidation, "validation"
	default:
		return ExitDatabase, "database"
	}
}

func hasJSON(args []string) bool {
	for _, arg := range args {
		if arg == "--json" || arg == "-json" || strings.HasPrefix(arg, "--json=") {
			return true
		}
	}
	return false
}
