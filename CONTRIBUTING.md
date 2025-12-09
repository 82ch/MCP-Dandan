# Contributing to MCP-Dandan

Thank you for your interest in contributing to MCP-Dandan! We welcome contributions from the community and appreciate your efforts to improve this project.

MCP-Dandan is an integrated monitoring service that observes MCP (Model Context Protocol) communications and detects security threats in real time. Your contributions help make this tool more robust and accessible to everyone.

## Ways to Contribute

We welcome various types of contributions:

- **Bug Reports**: Report issues you encounter while using MCP-Dandan
- **Feature Suggestions**: Propose new features or improvements
- **Documentation**: Improve or translate documentation
- **Code Contributions**: Fix bugs, implement features, or improve code quality
- **Tests**: Add or improve test coverage
- **Security**: Report security vulnerabilities responsibly

## Before You Start

### Check Existing Issues
- Search [existing issues](https://github.com/yourusername/MCP-Dandan/issues) to avoid duplicates
- Check if someone is already working on similar changes
- Join the discussion on related issues before starting work

### Discuss New Features
- For significant changes or new features, please open an issue first
- Discuss your proposal with maintainers before investing time in implementation
- This helps ensure your contribution aligns with the project's direction

### Branch Strategy
- `main`: Stable production branch
- `dev`: Development branch for integration
- `feature/*`: Feature branches (e.g., `feature/add-new-engine`)
- `bugfix/*`: Bug fix branches (e.g., `bugfix/fix-crash-on-startup`)

### Commit Message Convention
We follow [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
[Tag] Description
```

**Commit Types:**

| Tag Name | Description |
| --- | --- |
| Feat | Add a new feature |
| Fix | Fix a bug |
| !BREAKING CHANGE | Major API changes |
| !HOTFIX | Critical bug fix that needs immediate attention |
| Style | Code formatting changes, missing semicolons, whitespace removal, etc. |
| Refactor | Code refactoring (structural changes, performance improvements, readability improvements, etc.) |
| Comment | Add or modify necessary comments |
| Docs | Documentation changes |
| Test | Add or refactor test code, no changes to production code |
| Chore | Build task updates, package manager updates, configuration changes, etc., no changes to production code |
| Rename | Only renaming or moving files/folders |
| Remove | Only removing files |
| Init | Initial setup (creating controllers, request/response DTOs, etc.) |

**Examples:**
```
[Feat] Add SQL injection detection engine
[Fix] Resolve dashboard crash on empty data
[Docs] Update installation instructions
[!HOTFIX] Fix critical security vulnerability in auth module
[Refactor] Improve performance of detection engine
```

## Development Environment Setup

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/MCP-Dandan.git
cd MCP-Dandan
```

### 2. Version Requirements
- **Python**: 3.8 or higher
- **Node.js**: 18.x or higher
- **npm**: 8.x or higher

### 3. Install Dependencies
```bash
# Install all dependencies (Python + Node.js)
npm run install-all
```

### 4. Build and Test
```bash
# Run development server
npm run dev
```

### 5. Environment Configuration
- Copy `.env.example` to `.env` (if applicable)
- Set up your `MISTRAL_API_KEY` for Tool Poisoning Engine testing
- Configure your Claude Desktop or Cursor settings for testing

## Pull Request Guidelines
We use a structured PR template. Please fill out all sections:

- **Overview**: Brief summary of what changes this PR includes
- **Changes**: Detailed description of modifications/additions
- **Related Issues**: Link related issues (e.g., "Fixes #123", "Related to #45")
- **Additional Notes**: Points that need discussion or attention from reviewers

The PR template will be automatically loaded when you create a new pull request.


### Code Style
- **Python**: Follow PEP 8 guidelines
- **JavaScript/TypeScript**: Follow project's ESLint configuration
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions small and focused

### Before Submitting
- [ ] Test your changes thoroughly
- [ ] Update documentation if needed
- [ ] Add or update tests for new functionality
- [ ] Ensure all tests pass
- [ ] Follow the project's code style
- [ ] Update CHANGELOG.md if applicable



## Review Process

- Maintainers will review your PR as soon as possible
- Address review comments and push updates
- Once approved, a maintainer will merge your PR
- Be patient and respectful during the review process


## License

By contributing to MCP-Dandan, you agree that your contributions will be licensed under the [MIT License](LICENSE). All contributions will become part of the project and subject to the project's license terms.

---

## Questions?

If you have questions about contributing, feel free to:
- Open an issue with the `question` label
- Reach out to maintainers
- Check existing documentation

Thank you for contributing to MCP-Dandan! 🎉
