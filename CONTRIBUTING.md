# Contributing to Mina - Assistente Virtual Do G.E.R.A

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Enhancements](#suggesting-enhancements)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to:

- Use welcoming and inclusive language
- Be respectful of differing viewpoints
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally
3. Create a branch for your changes
4. Make your changes
5. Push to your fork and submit a pull request

## Development Setup

### Prerequisites

- Python 3.9 - 3.12
- Git
- System dependencies (PortAudio, libcurl)

### Installation

```bash
# Clone your fork
git clone https://github.com/YOUR-USERNAME/Mina-a-Assistente-Virtual-Do-G.E.R.A.git
cd Mina-a-Assistente-Virtual-Do-G.E.R.A

# Install system dependencies
# Ubuntu/Debian:
sudo apt-get install portaudio19-dev libcurl4-openssl-dev gcc

# macOS:
brew install portaudio curl

# Install Python dependencies
pip install -r requirements.txt

# Install development dependencies
pip install black flake8 isort pytest pytest-asyncio pytest-cov

# Build C extensions (optional, for STT/chat features)
gcc -shared -fPIC stt.c -o libs/stt/libstt.so -lportaudio -lcurl
gcc -shared -fPIC apicomm.c -o libs/apicomm/libapicomm.so -lcurl
```

### Running the Application

```bash
# Run GUI
python main_gui.py

# Run in fullscreen mode
python main_gui.py -f
```

## How to Contribute

### Types of Contributions

- **Bug Fixes**: Fix issues in existing code
- **Features**: Add new functionality
- **Documentation**: Improve or add documentation
- **Tests**: Add or improve test coverage
- **Code Quality**: Refactoring, optimization, cleanup

### Before You Start

1. Check if an issue already exists for your contribution
2. If not, create an issue to discuss your proposed changes
3. Wait for approval before starting significant work
4. Reference the issue number in your commits and PR

## Coding Standards

### Python Style Guide

This project follows **PEP 8** with some modifications defined in `.flake8` and `pyproject.toml`.

#### Code Formatting

We use `black` for code formatting:

```bash
# Format your code before committing
black .

# Check formatting
black --check .
```

#### Import Sorting

We use `isort` for import organization:

```bash
# Sort imports
isort .

# Check import order
isort --check-only .
```

#### Linting

We use `flake8` for linting:

```bash
# Run linter
flake8 .
```

### Code Style Guidelines

1. **Line Length**: Maximum 88 characters (black default)
2. **Imports**: Organized using isort (stdlib, third-party, local)
3. **Naming Conventions**:
   - Classes: `PascalCase`
   - Functions/methods: `snake_case`
   - Constants: `UPPER_SNAKE_CASE`
   - Private methods: `_leading_underscore`
4. **Docstrings**: Use Google style docstrings
5. **Type Hints**: Add type hints to function signatures
6. **Comments**: Write clear, concise comments for complex logic

### Example Code

```python
from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ExampleClass:
    """Brief description of the class.

    Longer description if needed, explaining the purpose
    and usage of this class.

    Attributes:
        attribute_name: Description of attribute
    """

    def __init__(self, param: str) -> None:
        """Initialize the class.

        Args:
            param: Description of parameter
        """
        self._param = param

    def public_method(self, value: int) -> Optional[str]:
        """Public method with clear purpose.

        Args:
            value: Description of what value represents

        Returns:
            Description of return value, or None if condition met

        Raises:
            ValueError: When value is negative
        """
        if value < 0:
            raise ValueError("Value must be non-negative")

        return f"{self._param}: {value}"
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_config_manager.py

# Run specific test
pytest tests/test_config_manager.py::test_singleton_pattern
```

### Writing Tests

- Place tests in `tests/` directory
- Name test files as `test_*.py`
- Name test functions as `test_*`
- Use descriptive test names
- Test one thing per test function
- Use fixtures for common setup

```python
import pytest
from src.utils.config_manager import ConfigManager


def test_config_manager_singleton():
    """Test that ConfigManager follows singleton pattern."""
    instance1 = ConfigManager()
    instance2 = ConfigManager()
    assert instance1 is instance2


@pytest.mark.asyncio
async def test_async_functionality():
    """Test asynchronous functionality."""
    # Your async test code here
    pass
```

## Pull Request Process

### Before Submitting

1. ✅ Code follows style guidelines (black, isort, flake8)
2. ✅ All tests pass
3. ✅ New code has tests
4. ✅ Documentation is updated
5. ✅ Commit messages are clear
6. ✅ Branch is up to date with main

### Commit Messages

Use clear, descriptive commit messages:

```
Short (50 chars or less) summary

More detailed explanatory text, if necessary. Wrap it to about 72
characters. The blank line separating the summary from the body is
critical.

- Bullet points are okay
- Use present tense ("Add feature" not "Added feature")
- Reference issue numbers: Fixes #123
```

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe the tests you ran and how to reproduce them

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass
```

### Review Process

1. Submit your PR
2. Wait for automated CI checks to complete
3. Address any CI failures
4. Respond to reviewer comments
5. Make requested changes
6. Wait for approval
7. PR will be merged by maintainers

## Reporting Bugs

### Before Reporting

1. Check if the bug has already been reported
2. Verify you're using the latest version
3. Test on a clean installation if possible

### Bug Report Template

```markdown
**Description**
Clear description of the bug

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What should happen

**Screenshots**
If applicable

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python Version: [e.g., 3.11]
- Application Version: [e.g., commit hash]

**Additional Context**
Any other relevant information
```

## Suggesting Enhancements

### Enhancement Request Template

```markdown
**Is your feature request related to a problem?**
Clear description of the problem

**Describe the solution you'd like**
Clear description of desired functionality

**Describe alternatives you've considered**
Other solutions you've thought about

**Additional context**
Mockups, examples, or other relevant information
```

## Project Structure

```
.
├── src/                    # Source code
│   ├── display/           # Display layer (GUI)
│   ├── utils/             # Utility modules
│   └── views/             # View components
├── config/                # Configuration files
├── assets/                # Static resources
├── libs/                  # Native libraries
├── models/                # ML models
├── keywords/              # Wake word files
├── tests/                 # Test suite
├── .github/              # GitHub workflows
└── docs/                 # Documentation
```

## Development Workflow

### Typical Workflow

1. **Create a branch**: `git checkout -b feature/your-feature-name`
2. **Make changes**: Edit code, add tests, update docs
3. **Format code**: `black . && isort .`
4. **Lint**: `flake8 .`
5. **Test**: `pytest`
6. **Commit**: `git commit -m "Add feature: description"`
7. **Push**: `git push origin feature/your-feature-name`
8. **Create PR**: Submit pull request on GitHub

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring
- `test/description` - Test improvements

## Getting Help

- **Issues**: Open an issue for bugs or questions
- **Discussions**: Use GitHub Discussions for general questions
- **Documentation**: Check README and docs/ directory

## Recognition

Contributors will be recognized in:
- Git commit history
- Release notes (for significant contributions)
- README.md (for major contributions)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to make this project better! 🚀
