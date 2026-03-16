

from __future__ import annotations
from typing import Any, Tuple, List
from dataclasses import dataclass, field, replace

from syncraft.ast import AST, Alt, Lazy, Many, Seq, Nothing, EOF, Unknown

from string import Formatter
import re
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
        self.format_string = self.preprocess(format_string, is_broken)
        self.multiple_line = '\n' in self.format_string


    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            if key == '@opt':
                return '\n' if self.is_broken else ' '
            
            elif '@' in key:
                # Supports {name@0} and {@0}
                _, idx = key.rsplit('@', 1)
                try:
                    int_idx = int(idx)
                    return args[int_idx]
                except (ValueError, IndexError):
                    return f"{{{key}}}"  # If index is out of range, return the placeholder as-is for debugging
        elif isinstance(key, int):
            if key < len(args):
                return args[key]
            else:
                return f"{{{key}}}"  # If index is out of range, return the placeholder as-is for debugging            
        return super().get_value(key, args, kwargs)
    
    def __call__(self, *args: Any, **kwargs: Any) -> str:
        return self.format(self.format_string, *args, **kwargs)


class TemplatedText:
    def __init__(self, template: TemplateFormatter | None) -> None:
        self.template = template
        self.text: List[str] | None = None
    
    def __call__(self, *args: Any, **kwargs: Any) -> List[str]:
        if self.text is None:
            if self.template is None:
                parts = [str(a) for a in args]
                parts.extend(str(v) for v in kwargs.values())
                self.text = "".join(parts).split('\n')
            else:
                self.text = self.template(*args, **kwargs).split('\n')
        return self.text
    

    
@dataclass(frozen=True, slots=True)
class RenderState:
    width: int = field(default=80)
    col: int = field(default=0)
    depth: int = field(default=0)
    flat: bool = field(default=True)
    indent: str = field(default="    ")
    def fit(self, text: List[str]) -> bool:
        return all(self.col + self.depth * len(self.indent) + len(line) <= self.width for line in text)


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
    flat: TemplatedText = field(default_factory=lambda: TemplatedText(None), repr=False, compare=False, hash=False )
    broken: TemplatedText = field(default_factory=lambda: TemplatedText(None), repr=False, compare=False, hash=False )
    ast: AST | Any = field(default=None, repr=False, compare=False, hash=False)
    include_all: bool = True

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
                return value.text
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
    
    def fit(self, state: RenderState) -> bool:
        raise NotImplementedError("fits() is not implemented yet, since the current renderer doesn't support soft line breaks. It will be implemented in the future when we add support for soft line breaks.")

    def txt(self, state: RenderState) -> Tuple[List[str], RenderState]:
        raise NotImplementedError("txt() is not implemented yet, since the current renderer doesn't support soft line breaks. It will be implemented in the future when we add support for soft line breaks.")

    def render(self, *, width: int = 80, indent: str = "    ") -> str:
        init_state = RenderState(width=width, indent=indent)
        txt, _ = self.txt(init_state)
        return "\n".join(txt).strip()

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

    def txt(self, state: RenderState) -> Tuple[List[str], RenderState]:
        ret = self.flat(self.value) if state.flat else self.broken(self.value)
        if len(ret) > 0:
            return ret, replace(state, col=state.col + len(ret[-1]))
        else:
            return ret, state
    
    def fit(self, state: RenderState) -> bool:
        return replace(state, flat=True).fit(self.flat(self.value)) 


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
        

    def txt(self, state: RenderState) -> Tuple[List[str], RenderState]:
        chunks: list[str] = []
        cur_state = state
        for part, keep in self.parts:
            txt, cur_state = part.txt(cur_state)
            if txt and (keep or self.include_all):
                chunks.append("\n".join(txt))
        if not chunks:
            return [], cur_state
        else:
            ret = self.flat(*chunks) if state.flat else self.broken(*chunks)
            return ret, replace(cur_state, col=cur_state.col + len(ret[-1]) if ret else cur_state.col)
    
    def fit(self, state: RenderState) -> bool:
        flat_state = replace(state, flat=True)
        chunks: list[str] = []
        cur_state = flat_state
        for part, keep in self.parts:
            txt, cur_state = part.txt(cur_state)
            if keep or self.include_all:
                chunks.extend(txt)
        ret = self.flat(*chunks)
        return flat_state.fit(ret)
    
@dataclass
class Group(LayoutDoc):
    """
    Width-sensitive choice: flat mode if it fits, otherwise break mode.
    """
    body: LayoutDoc = field(default_factory=LayoutDoc)
    level: int = 0


    def txt(self, state: RenderState) -> Tuple[List[str], RenderState]:
        use_flat = self.fit(state)
        group_state = replace(state, depth=state.depth + max(0, self.level), flat=use_flat)
        txt, rendered_state = self.body.txt(group_state)
        prefix = state.indent * state.depth if not use_flat else ''
        return [prefix + t for t in txt], replace(rendered_state, flat=state.flat)
    
    def fit(self, state: RenderState) -> bool:
        return self.body.fit(replace(state, flat=True))



