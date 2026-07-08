### Go
(write "golang" in stack.md to pull this pack)
- Handle every error — `if err != nil` is not optional at a hackathon either;
  wrap with `%w` for context.
- gofmt + go vet clean before push; define small interfaces at the consumer.
- Every goroutine needs an exit path (context cancellation) — leaked
  goroutines eat the demo box.
- Table-driven tests for anything on the demo path.
