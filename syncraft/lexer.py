from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple, List, Iterable
import re
from enum import Enum, auto


class MatchStatus(Enum):
    FULL = auto()      # a complete token is recognized
    POSSIBLE = auto()  # could become a token with more input
    DEAD = auto()      # cannot match here


@dataclass(frozen=True)
class MatchResult:
    status: MatchStatus
    end: int = 0                 # valid iff status == FULL
    type: Optional[str] = None   # token type if FULL


class TokenMatcher:
    """Interface for token recognizers starting at buffer[0]."""

    def match(self, buffer: str) -> MatchResult:
        raise NotImplementedError

    # Optionally, a hook to say “I need at least N chars before judging”
    min_prefix: int = 1


# ---------- Simple anchored-regex matcher (FULL or DEAD only) ----------

class RegexToken(TokenMatcher):
    """Anchored regex: FULL if re.match succeeds, else DEAD.
       No POSSIBLE state — that’s handled by orchestrator combining matchers.
    """
    def __init__(self, name: str, pattern: str):
        self.name = name
        self.re = re.compile(rf'(?:{pattern})')

    def match(self, buffer: str) -> MatchResult:
        m = self.re.match(buffer)   # anchored at pos 0
        if m:
            return MatchResult(MatchStatus.FULL, end=m.end(), type=self.name)
        return MatchResult(MatchStatus.DEAD)


# ---------- Stateful matcher for tokens that need partial awareness ----------

class StringLiteral(TokenMatcher):
    """Double-quoted strings with C-style escapes: " ... "
       Returns POSSIBLE while unterminated.
    """
    def __init__(self, name: str = "STRING"):
        self.name = name

    def match(self, buffer: str) -> MatchResult:
        if not buffer or buffer[0] != '"':
            return MatchResult(MatchStatus.DEAD)

        i = 1
        escaped = False
        while i < len(buffer):
            ch = buffer[i]
            if escaped:
                escaped = False
                i += 1
                continue
            if ch == '\\':
                escaped = True
                i += 1
                continue
            if ch == '"':
                return MatchResult(MatchStatus.FULL, end=i + 1, type=self.name)
            i += 1
        # Ran out of input with open quote → could still complete
        return MatchResult(MatchStatus.POSSIBLE)


class BlockComment(TokenMatcher):
    """/* ... */ with nesting disabled. POSSIBLE until closing */ appears."""
    def __init__(self, name: str = "COMMENT"):
        self.name = name

    def match(self, buffer: str) -> MatchResult:
        if not buffer.startswith("/*"):
            return MatchResult(MatchStatus.DEAD)
        i = 2
        while i < len(buffer):
            if buffer[i-1] == '*' and buffer[i] == '/':
                return MatchResult(MatchStatus.FULL, end=i+1, type=self.name)
            i += 1
        return MatchResult(MatchStatus.POSSIBLE)


# ---------- The streaming lexer orchestrator (no rollback) ----------

@dataclass
class Token:
    type: str
    lexeme: str


class StreamingLexer:
    def __init__(self, matchers: List[TokenMatcher], *, prioritize: List[str] | None = None):
        self.matchers = matchers
        self.buffer = ""
        # optional priority: if two FULL matches have the same end, pick the one with higher priority
        self.priority = {t: i for i, t in enumerate(prioritize or [])}

    def feed(self, chunk: str) -> None:
        """Push-mode: append input. Then try to emit as many tokens as possible."""
        self.buffer += chunk

    def _choose_longest(self, fulls: List[MatchResult]) -> MatchResult:
        # Max by end; tie-break by priority (lower index = higher priority)
        best = None
        for m in fulls:
            if best is None:
                best = m
                continue
            if m.end > best.end:
                best = m
            elif m.end == best.end:
                pr_m = self.priority.get(m.type or "", 1_000_000)
                pr_b = self.priority.get(best.type or "", 1_000_000)
                if pr_m < pr_b:
                    best = m
        return best

    def tokens(self, *, flush: bool = False) -> Iterable[Token]:
        """Yield as many tokens as deterministically available from the buffer.
           If flush=True (EOF), emit partials as errors if still POSSIBLE.
        """
        while self.buffer:
            results = [m.match(self.buffer) for m in self.matchers]

            fulls = [r for r in results if r.status == MatchStatus.FULL and r.end > 0]
            possibles = any(r.status == MatchStatus.POSSIBLE for r in results)

            if fulls:
                best = self._choose_longest(fulls)
                lexeme = self.buffer[:best.end]
                self.buffer = self.buffer[best.end:]
                yield Token(best.type or "UNKNOWN", lexeme)
                continue

            if possibles and not flush:
                # Need more input to decide; stop for now
                return

            # No FULL; either no POSSIBLE or we are at EOF (flush). Lexing error recovery:
            # Emit one-character ERROR token and move on.
            yield Token("ERROR", self.buffer[0])
            self.buffer = self.buffer[1:]

    def flush(self) -> Iterable[Token]:
        """Signal EOF and drain remaining tokens (converting lingering POSSIBLE to ERROR)."""
        yield from self.tokens(flush=True)
        # After flush, buffer should be empty or only errors remain



def test()->None:
    matchers = [
        RegexToken("WS",      r"[ \t\r\n]+"),
        RegexToken("IDENT",   r"[A-Za-z_][A-Za-z0-9_]*"),
        RegexToken("NUMBER",  r"\d+"),
        RegexToken("EQ",      r"="),
        StringLiteral("STRING"),
        BlockComment("COMMENT"),
    ]

    lex = StreamingLexer(matchers, prioritize=["IDENT", "NUMBER", "STRING", "COMMENT", "WS"])

    # Simulate streaming input
    lex.feed('foo = "hel')
    print([t.__dict__ for t in lex.tokens()])   # no output yet (string POSSIBLE)

    lex.feed('lo" /*ab')
    print([t.__dict__ for t in lex.tokens()])   # emits: IDENT 'foo', WS ' ', EQ '=', WS ' ', STRING '"hello"'
                                                # comment still POSSIBLE

    lex.feed('cd*/ 123')
    print([t.__dict__ for t in lex.tokens()])   # emits: COMMENT '/*abcd*/', WS '  ', NUMBER '123'

    lex.feed(' hel')
    # End of stream
    print([t.__dict__ for t in lex.tokens()])    

    lex.feed('lo ')
    print([t.__dict__ for t in lex.flush()])    # drain any leftovers (errors if unterminated)
