

from __future__ import annotations
from typing import Any, Tuple, List, Dict
from dataclasses import dataclass, field, replace

from syncraft.ast import AST, Alt, Lazy, Many, Seq, Nothing, EOF, Unknown

from string import Formatter
import re


class OverflowError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class RenderState:
    width: int = field(default=80)
    indent: int = field(default=0)
    col: int = field(default=0)

    def with_indent(self, indent: int) -> RenderState:
        return replace(self, indent=indent)
    
    def append(self, text: str,*, check_overflow: bool) -> Tuple[str, RenderState]:
        results = []
        tmp = text.split('\n')
        col = self.col
        for i, s in enumerate(tmp):
            if i == 0:
                results.append(s)
                col += len(s)
            else:
                results.append(' ' * self.indent + s)
                col = self.indent + len(s)
            if check_overflow and col > self.width:
                raise OverflowError(f"Overflow Error: text '{text}' exceeds the available width {self.width} at column {col}")
        return '\n'.join(results), replace(self, col=col)

    



class TemplateFormatter(Formatter):
    r"""
    1. '\n' => hard line break
    2. {@opt} => soft line break
    3. {name@1} => the second positional argument == {1}, the name is optional and for readability only
    4. {b?static text} => only appears in the broken mode, static text can not be placeholder, it is emitted as-is if the mode matches, otherwise the whole block is deleted
    5. {f?static text} => only appears in the flat mode, static text can not be placeholder, it is emitted as-is if the mode matches, otherwise the whole block is deleted
    6. '\}' => literal '}}' only inside conditionals's static text, since outside of conditionals '}' is not special
    7. '\{' => literal '{{' only inside conditionals's static text, since outside of conditionals '{' is not special
    """
    @staticmethod
    def preprocess(format_string: str, is_broken: bool) -> str:
        format_string = format_string.replace(r'\n', '\n')

        # 2. Process Conditionals
        def process_cond(match):
            prefix, content = match.group(1), match.group(2)
            
            if (prefix == 'b?' and is_broken) or (prefix == 'f?' and not is_broken):
                # Escape braces for string.Formatter: { -> {{ and \} -> }}
                # We also handle \{ -> {{ just in case the user escaped the opening one too
                content = content.replace(r'\{', '{{')
                content = content.replace(r'\}', '}}')
                return content
            return '' # Mode doesn't match, delete the whole block
        # Matches {b? or {f? followed by anything until a } NOT preceded by \
        cond_regex = re.compile(r'\{(b\?|f\?)(.*?)(?<!\\)\}', re.DOTALL)
        format_string = cond_regex.sub(process_cond, format_string)
        return format_string

    def __init__(self, format_string: str, is_broken: bool) -> None:
        super().__init__()
        self.is_broken = is_broken
        self.original_format_string = format_string
        self.format_string = self.preprocess(format_string, is_broken)
        self.multiple_line = '\n' in self.format_string


    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            if key == '@opt':
                return '\n' if self.is_broken else ''
            
            elif '@' in key:
                # Supports {name@0} and {@0}
                _, idx = key.rsplit('@', 1)
                try:
                    int_idx = int(idx)
                    return args[int_idx]
                except (ValueError, IndexError):
                    return f"{{{key}}}"  # If index is out of range, return the placeholder as-is for debugging
            else:
                try:
                    int_idx = int(key)
                    return args[int_idx]
                except (ValueError, IndexError):
                    return f"{{{key}}}"  # If index is out of range, return the placeholder as-is for debugging
        elif isinstance(key, int):
            if key < len(args):
                return args[key]
            else:
                return f"{{{key}}}"  # If index is out of range, return the placeholder as-is for debugging            
        return super().get_value(key, args, kwargs)
        
    
    def __call__(self, flat: bool, state: RenderState,  *args: str) -> Tuple[str, RenderState]:
        ret = []
        for literal, field_name, _, _ in self.parse(self.format_string):
            if literal:
                s, state = state.append(literal, check_overflow= flat)
                ret.append(s)
            if field_name is not None:
                val = self.get_value(field_name, args, {})
                s, state = state.append(val, check_overflow= flat)
                ret.append(s)
        return ''.join(ret), state

    def __repr__(self) -> str:
        return f"<pattern={self.original_format_string!r}>"
    
    def __str__(self) -> str:
        return self.original_format_string




@dataclass
class TemplatedText:
    """
    A template that can be called with arguments to produce formatted text.
    
    This class is designed to be created freshly for each LayoutDoc instance
    (see LayoutDoc.template()). The text result is cached after the first call
    to __call__() - subsequent calls with the same arguments will return the
    cached result.
    
    Important: Each TemplatedText instance should only be used with a single
    set of arguments (e.g., one specific value or one specific set of chunks).
    Reusing the same instance with different arguments will return stale cached
    results from the first call.
    
    For this reason, LayoutDoc.template() creates new TemplatedText instances
    for each call, ensuring each document has its own template with its own cache.
    """
    template: TemplateFormatter | None
    
    def __call__(self, flat: bool,  state: RenderState, *args: str) -> Tuple[str, RenderState]:
        """
        Format the given arguments using the template.
        
        Note: The result is cached in self.text after the first call.
        Subsequent calls with the same arguments return the cached result.
        This is intentional - TemplatedText is designed to be created freshly
        for each use case (see class docstring).
        """
        if self.template is None:
            # Merge logic: if no template, just use the absolute positions
            return state.append(''.join(args), check_overflow=flat)
        else:
            return self.template(flat, state, *args)
                



def construct_templated_text(template: str|None, is_broken: bool) -> TemplatedText:
    if template is None:
        return TemplatedText(None)
    else:
        return TemplatedText(TemplateFormatter(template, is_broken))

@dataclass
class LayoutDoc:
    """
    Base layout document.
    Layout documents are rendered via `render(...)`, callers can
    supply constraints like max line width.
    """
    flat: TemplatedText = field(default_factory=lambda: TemplatedText(None),  compare=False, hash=False )
    broken: TemplatedText = field(default_factory=lambda: TemplatedText(None),  compare=False, hash=False )
    ast: AST | Any = field(default=None, repr=False, compare=False, hash=False)
    include_all: bool = True

    def interesting(self) -> bool:
        return False
    
    def with_all(self, include_all: bool = True) -> LayoutDoc:
        self.include_all = include_all
        return self

    def template(self, template: str|None) -> LayoutDoc:
        self.flat = construct_templated_text(template, is_broken=False)
        self.broken = construct_templated_text(template, is_broken=True)
        return self

    def with_ast(self, ast: AST | Any) -> LayoutDoc:
        self.ast = ast
        return self

    @classmethod
    def from_ast(cls, value: Any) -> LayoutDoc:
        """
        Build LayoutDoc from AST tree
        """
        def terminal(value: Any) -> str:
            if isinstance(value, str):
                return value
            elif isinstance(value, bytes):
                return value.decode('utf-8', errors='replace')
            elif hasattr(value, "text"):
                return str(value.text)
            elif isinstance(value, (Nothing, EOF, Unknown)):
                return ""
            else:
                return str(value)
                                  
        if isinstance(value, LayoutDoc):
            return value
        elif isinstance(value, Lazy):
            return LayoutDoc.from_ast(value.value).with_ast(value)
        elif isinstance(value, Alt):
            if value.value is None:
                return Text(value="", ast=value)
            else:
                return LayoutDoc.from_ast(value.value).with_ast(value)
        elif isinstance(value, Many):
            return Concat(parts=tuple((LayoutDoc.from_ast(item), True) for item in value.value), ast=value)
        elif isinstance(value, Seq):
            return Concat(parts=tuple((LayoutDoc.from_ast(item), keep) for item, keep in value.value), ast=value)
        return Text(value=terminal(value), ast=value)
    

    def txt(self, state: RenderState, flat: bool) -> Tuple[str, RenderState]:
        raise NotImplementedError("txt() is not implemented for the base LayoutDoc class. Please use a subclass like Text, Group, or Concat.")
            
    def render(self, width: int = 80) -> str:
        state = RenderState(width=width, col=0)
        tmp = Group(body=self) if not isinstance(self, Group) else self
        s, state = tmp.txt(state, flat=True)
        return s

@dataclass    
class Text(LayoutDoc):
    """
    Literal text fragment.
    Unbreakable: it always renders as-is, without line breaks, 
    even if it exceeds the available width.

    This is the atomic unit of rendering: 
    it has a fixed width equal to the length of its text content.
    """
    value: str = ""

    def txt(self, state: RenderState, flat: bool) -> Tuple[str, RenderState]:
        return self.flat(flat, state, self.value) if flat else self.broken(flat, state, self.value)
    



@dataclass
class Group(LayoutDoc):
    """
    Width-sensitive choice: flat mode if it fits, otherwise break mode.
    """
    body: LayoutDoc = field(default_factory=LayoutDoc)
    indent: int = 0


    def txt(self, state: RenderState, flat: bool) -> Tuple[str, RenderState]:
        render_state1 = replace(state, indent=state.indent + self.indent)
        if not flat:
            return self.body.txt(render_state1, flat=False)
        else:
            try:
                return self.body.txt(render_state1, flat=True)
            except OverflowError:
                # Try broken mode - won't raise even if content exceeds width
                return self.body.txt(render_state1, flat=False)
    


@dataclass
class Concat(LayoutDoc):
    """
    Concatenation node: render each part left-to-right.
    The width of a Concat is the sum of the widths of its parts 
    if it doesn't contain Line.

    If it contains Line, its width is unbounded, 
    since Line can break into multiple lines.

    This class doesn't break lines by itself, but it can contain Line nodes that do.
    """
    parts: Tuple[Tuple[LayoutDoc, bool], ...] = field(default_factory=tuple)
        


    def txt(self, state: RenderState, flat: bool) -> Tuple[str, RenderState]:
        chunks: list[str] = []
        current_state = state
        for part, keep in self.parts:
            if keep or self.include_all:
                
                txt, current_state = part.txt(current_state, flat)
                chunks.append(txt)
        if flat:
            return self.flat(flat, state, *chunks)
        else:
            return self.broken(flat, state, *chunks)
        
        

    



