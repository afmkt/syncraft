from __future__ import annotations

import io

from syncraft.input import StreamCursor
from syncraft.parser import parse as parser_run
from syncraft.parser import ParserState, Runner
from syncraft.syntax import Syntax


S = Syntax


def test_stream_cursor_string_basic_chunks() -> None:
    cursor = StreamCursor.from_data("abcdef", chunk_size=2)

    chunk1, final1 = cursor.next_chunk()
    chunk2, final2 = cursor.next_chunk()
    chunk3, final3 = cursor.next_chunk()

    assert chunk1 == "ab"
    assert not final1
    assert chunk2 == "cd"
    assert not final2
    assert chunk3 == "ef"
    assert final3


def test_stream_cursor_bytes_basic_chunks() -> None:
    cursor = StreamCursor.from_data(b"12345", chunk_size=2)

    chunk1, final1 = cursor.next_chunk()
    chunk2, final2 = cursor.next_chunk()
    chunk3, final3 = cursor.next_chunk()

    assert chunk1 == b"12"
    assert not final1
    assert chunk2 == b"34"
    assert not final2
    assert chunk3 == b"5"
    assert final3


def test_stream_cursor_empty_input_is_final() -> None:
    cursor = StreamCursor.from_data("", chunk_size=4)

    chunk, final = cursor.next_chunk()

    assert chunk == ""
    assert final


def test_runner_resume_initial_state_from_cursor() -> None:
    runner = Runner()
    cursor = StreamCursor.from_data("hello", chunk_size=5)

    state = runner.resume(request=None, cursor=cursor)

    assert state.input == "hello"
    assert state.index == 0
    assert state.final


def test_runner_resume_extends_existing_state() -> None:
    runner = Runner()
    state: ParserState[str] = ParserState(input="ab", index=2, base=0, final=False)
    cursor = StreamCursor.from_data("cd", chunk_size=2)

    updated = runner.resume(request=state, cursor=cursor)

    assert updated.input == "abcd"
    assert updated.index == 2
    assert updated.final


def test_parser_state_pending_and_ended_flags() -> None:
    pending_state: ParserState[str] = ParserState(input="ab", index=2, base=0, final=False)
    ended_state: ParserState[str] = ParserState(input="ab", index=2, base=0, final=True)

    assert pending_state.pending
    assert not pending_state.ended
    assert not ended_state.pending
    assert ended_state.ended


def test_parse_with_stream_cursor_chunks() -> None:
    syntax = S.rp(r"[a-z]+")
    cursor = StreamCursor.from_data("hello", chunk_size=2)

    result = parser_run(syntax=syntax, data=cursor)

    assert result == "hello"


def test_stream_cursor_from_text_io_returns_tuple_chunks() -> None:
    stream = io.StringIO("hello world")
    cursor = StreamCursor.from_stream(stream, mode="text", chunk_size=5)

    chunk, final = cursor.next_chunk()

    assert isinstance(chunk, tuple)
    assert len(chunk) >= 1
    assert final
