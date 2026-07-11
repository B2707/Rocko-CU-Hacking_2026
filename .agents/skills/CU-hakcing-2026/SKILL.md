```markdown
# CU-hakcing-2026 Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development conventions and workflows used in the CU-hakcing-2026 TypeScript codebase. It covers file naming, import/export styles, commit message standards, and testing patterns to ensure consistency and maintainability across the project. While no frameworks are detected, the repository follows modern TypeScript best practices.

## Coding Conventions

### File Naming
- Use **camelCase** for filenames.
  - Example: `userProfile.ts`, `dataFetcher.ts`

### Import Style
- Use **relative imports** for referencing other modules within the project.
  - Example:
    ```typescript
    import { fetchData } from './dataFetcher';
    ```

### Export Style
- Use **named exports** to expose functions, classes, or constants.
  - Example:
    ```typescript
    // In userProfile.ts
    export function getUserProfile(id: string) { ... }
    ```

### Commit Messages
- Follow **Conventional Commits** with the `feat` prefix for new features.
  - Example:
    ```
    feat: add user authentication middleware
    ```
- Average commit message length is ~70 characters.

## Workflows

### Feature Development
**Trigger:** When adding a new feature to the codebase  
**Command:** `/feature-dev`

1. Create a new branch for your feature.
2. Implement the feature using camelCase file naming and relative imports.
3. Use named exports for all new modules.
4. Write or update relevant tests in `*.test.*` files.
5. Commit changes using the `feat` prefix and a descriptive message.
6. Open a pull request for review.

### Code Testing
**Trigger:** When verifying code correctness  
**Command:** `/run-tests`

1. Identify or create test files matching the `*.test.*` pattern.
2. Run the test suite using the project's test runner (framework unknown; see project docs or package.json for details).
3. Ensure all tests pass before merging code.

## Testing Patterns

- Test files follow the `*.test.*` naming convention (e.g., `userProfile.test.ts`).
- The specific testing framework is unknown; refer to project documentation for setup and usage.
- Place tests alongside the modules they test or in a dedicated `tests` directory.

**Example test file:**
```typescript
// userProfile.test.ts
import { getUserProfile } from './userProfile';

describe('getUserProfile', () => {
  it('returns user data for a valid ID', () => {
    // test implementation
  });
});
```

## Commands
| Command        | Purpose                                   |
|----------------|-------------------------------------------|
| /feature-dev   | Start a new feature development workflow   |
| /run-tests     | Run the test suite for the codebase       |
```
