// Hacker Tracker read-only host scanner (Month 4 Phase 4).
//
// Stdlib-only by design: the scanner ships to third-party hosts, so we keep the
// dependency surface (and therefore the supply-chain / signing review) minimal.
// Do not add third-party modules without the same explicit approval the backend
// requires.
module github.com/firegiant9000/hacker-tracker/agent

go 1.22
