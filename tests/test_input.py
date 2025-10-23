from __future__ import annotations

import asyncio
import io
from pathlib import Path
from typing import Any, AsyncIterator, Iterator, Sequence, cast

import pytest

from syncraft.input import (
    Input,
    StringInput,
    BytesInput,
    IteratorInput,
    AsyncIteratorInput,
    AsyncTextStream,
)


def test_string_input_reads_chunks_and_sets_eof() -> None:
    stream = StringInput("abcd")

    first = stream.read(2)
    assert first == "ab"
    assert not stream.eof

    second = stream.read(2)
    assert second == "cd"
    assert stream.eof

    with pytest.raises(EOFError):
        stream.read(1)


def test_bytes_input_read_all_and_eof() -> None:
    stream = BytesInput(b"xyz")

    payload = stream.read()
    assert payload == b"xyz"
    assert stream.eof

    with pytest.raises(EOFError):
        stream.read(1)


def test_iterator_input_respects_chunk_size() -> None:
    data_iter: Iterator[int] = iter([1, 2, 3])
    stream: IteratorInput[int] = IteratorInput(data_iter)

    first = stream.read(2)
    assert first == (1, 2)
    assert not stream.eof

    second = stream.read(2)
    assert second == (3,)
    assert stream.eof

    with pytest.raises(EOFError):
        stream.read(1)


def test_async_iterator_input_reads_and_marks_eof() -> None:
    async def run() -> None:
        async def agen() -> AsyncIterator[int]:
            for item in (1, 2, 3):
                yield item

        stream: AsyncIteratorInput[int] = AsyncIteratorInput(agen(), payload_kind='token')

        first = await stream.aread(2)
        assert first == (1, 2)
        assert not stream.eof

        second = await stream.aread(2)
        assert second == (3,)
        assert stream.eof

        with pytest.raises(EOFError):
            await stream.aread(1)

    asyncio.run(run())


def test_input_from_data_dispatches_correct_types() -> None:
    from_str = Input.from_data("hello")
    assert isinstance(from_str, StringInput)

    from_bytes = Input.from_data(b"hello")
    assert isinstance(from_bytes, BytesInput)

    from_sequence = Input.from_data([1, 2, 3])
    assert isinstance(from_sequence, IteratorInput)

    from_iterator = Input.from_data(iter([1, 2]))
    assert isinstance(from_iterator, IteratorInput)

    async def agen() -> AsyncIterator[int]:
        for item in (1, 2):
            yield item

    from_async = Input.from_data(agen())
    assert isinstance(from_async, AsyncIteratorInput)


def test_input_from_stream_text_and_binary() -> None:
    text_source = io.StringIO("abcdef")
    text_input = Input.from_stream(text_source, blocksize=2, mode="text")
    assert isinstance(text_input, IteratorInput)
    chunks = text_input.read(1)
    assert chunks == ("ab",)
    remainder_chunks = cast(Sequence[str], text_input.read())
    remainder = "".join(remainder_chunks)
    assert remainder == "cdef"
    assert text_input.eof

    binary_source = io.BytesIO(b"0123")
    binary_input = Input.from_stream(binary_source, blocksize=2, mode="binary")
    assert isinstance(binary_input, IteratorInput)
    chunk = binary_input.read(1)
    assert chunk == (b"01",)
    rest_chunks = cast(Sequence[bytes], binary_input.read())
    rest = b"".join(rest_chunks)
    assert rest == b"23"
    assert binary_input.eof


def test_input_from_path_text_and_binary(tmp_path: Path) -> None:
    text_dir = tmp_path / "data"
    text_dir.mkdir()
    text_path = text_dir / "sample.txt"
    text_path.write_text("hello")
    text_input = Input.from_path(text_path, mode="text", blocksize=2)
    assert isinstance(text_input, IteratorInput)
    text_chunks = cast(Sequence[str], text_input.read())
    text_result = "".join(text_chunks)
    assert text_result == "hello"

    bin_dir = tmp_path / "binary"
    bin_dir.mkdir()
    bin_path = bin_dir / "sample.bin"
    bin_path.write_bytes(b"abcd")
    bin_input = Input.from_path(bin_path, mode="binary", blocksize=2)
    assert isinstance(bin_input, IteratorInput)
    bin_chunks = cast(Sequence[bytes], bin_input.read())
    bin_result = b"".join(bin_chunks)
    assert bin_result == b"abcd"

    with pytest.raises(ValueError):
        Input.from_path(text_path, mode=cast(Any, "invalid"))


def test_async_text_stream_reads_chunks_and_reports_eof() -> None:
    async def run() -> None:
        reader = asyncio.StreamReader()
        stream = AsyncTextStream(reader)

        async def producer() -> None:
            reader.feed_data(b"hello ")
            await asyncio.sleep(0)
            reader.feed_data(b"world")
            reader.feed_eof()

        producer_task = asyncio.create_task(producer())

        first = await stream.aread(5)
        assert first == "hello"

        remainder = await stream.aread()
        assert remainder == " world"
        assert stream.eof

        with pytest.raises(EOFError):
            await stream.aread(1)

        await producer_task

    asyncio.run(run())
