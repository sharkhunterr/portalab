# Portalab

## Git

- Commits use the repository owner's configured Git identity: never change `git user.name` / `git user.email`, never use Claude Code or Anthropic as author.
- Never add a "Co-Authored-By" line, nor any mention of Claude, Claude Code or Anthropic (no "Generated with…" text) in commit messages, pull requests or code.
- Create commits only when the current workflow asks for it.
- Never push, force-push, rewrite published history, delete branches, create releases or merge pull requests unless explicitly asked.

## Releases

- Releases are cut from this root with `npm run release:full` (standard-version → `vX.Y.Z` tag → the GitLab tag
  pipeline in `.gitlab-ci.yml`: validate, test, Docker build, Docker Hub, GitHub mirror, GitLab + GitHub releases).
- Before every release, write the new version's notes **in English** as a `# vX.Y.Z` block at the top of
  `GITHUB_RELEASES.md`: they are the release pages, and the release script refuses to run without them.
- README, release notes and the Docker Hub page (`portalab/deploy/DOCKERHUB.md`) are written in English.
- Brand assets (`assets/`) use Portalab's default theme palette; re-render them with `npm run assets`.
