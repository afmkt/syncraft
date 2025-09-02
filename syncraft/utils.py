"""
Optional syntax visualization using railroad-diagram.
Install with: pip install railroad-diagram
"""

from typing import Any

try:
    import railroad
except ImportError:
    railroad = None

class RailroadNotAvailable(Exception):
    pass

def visualize_syntax(syntax: Any, **kwargs) -> 'railroad.Diagram':
    """
    Visualize a syntax object as a railroad diagram.
    Requires railroad-diagram to be installed.

    Args:
        syntax: The syntax object to visualize.
        **kwargs: Additional options for diagram rendering.

    Returns:
        railroad.Diagram object.

    Raises:
        RailroadNotAvailable: If railroad-diagram is not installed.
    """
    if railroad is None:
        raise RailroadNotAvailable("railroad-diagram is not installed. Install with 'pip install railroad-diagram'.")
    # Example: convert your syntax object to railroad elements
    # This is a stub. You need to implement conversion from your Syntax type to railroad elements.
    # For demonstration, we'll just create a simple diagram.
    # Replace this with your actual conversion logic.
    diagram = railroad.Diagram(railroad.Sequence(
        railroad.Terminal(str(syntax)),
    ))
    return diagram

# Example usage:
# from syncraft.util import visualize_syntax
# diagram = visualize_syntax(my_syntax)
# diagram.writeSvg(open('syntax.svg', 'w'))
