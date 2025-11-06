"""
Pytest configuration to enable randomization in cache behavior for all tests.

This ensures that all tests run with randomized set iteration order to detect
any order-dependent bugs in the parser cache implementation.
"""

from syncraft.cache import set_randomization, set_random_seed

def pytest_sessionstart(session):
    """Called after the Session object has been created."""
    # Enable randomization for all tests
    set_randomization(True)
    
    # Set a fixed seed for reproducible test runs
    # You can change this seed or make it configurable via command line
    set_random_seed(42)
    
    print("\n[Cache Randomization] Enabled with seed=42")

def pytest_runtest_setup(item):
    """Called before each test item is executed."""
    # Ensure randomization is enabled for each test
    # This handles cases where individual tests might have disabled it
    set_randomization(True)

# Optional: Add command line option to control randomization
def pytest_addoption(parser):
    """Add command line options for randomization control."""
    parser.addoption(
        "--disable-randomization",
        action="store_true",
        default=False,
        help="Disable cache randomization for deterministic testing"
    )
    parser.addoption(
        "--random-seed",
        type=int,
        default=42,
        help="Set random seed for reproducible randomized tests"
    )

def pytest_configure(config):
    """Configure pytest based on command line options."""
    if config.getoption("--disable-randomization"):
        set_randomization(False)
        print("\n[Cache Randomization] Disabled via command line")
    else:
        seed = config.getoption("--random-seed")
        set_randomization(True)  # Explicitly enable for testing
        set_random_seed(seed)
        print(f"\n[Cache Randomization] Enabled with seed={seed}")