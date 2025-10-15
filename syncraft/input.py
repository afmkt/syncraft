from __future__ import annotations
from typing import Generic, Iterator, Optional, TypeVar, Sequence, AsyncIterator, Union, Literal, cast, Tuple
import io
import asyncio
import codecs
from pathlib import Path
from syncraft.ast import SyncraftError



T = TypeVar("T")
Chunk = Union[Sequence[T], str, bytes]
class Input(Generic[T]):
    def __init__(self, *, payload_kind: str) -> None:
        self._payload_kind: str = payload_kind

    def read(self, n: Optional[int] = None) -> Chunk:
        raise NotImplementedError
    
    async def aread(self, n: Optional[int] = None) -> Chunk:
        return self.read(n)
    
    @property
    def eof(self) -> bool:
        raise NotImplementedError

    @property
    def payload_kind(self) -> str:
        return self._payload_kind

    def mark_payload_kind(self, kind: str) -> None:
        self._payload_kind = kind
    
    @staticmethod
    def from_data(data: Union[str, bytes, Iterator[T], AsyncIterator[T], Sequence[T]]) -> Input[str] | Input[bytes] | Input[T]:
        if isinstance(data, str):
            return StringInput(data)
        elif isinstance(data, bytes):
            return BytesInput(data)
        elif isinstance(data, Sequence):
            payload_kind = "token"
            return IteratorInput(cast(Iterator[T], iter(data)), payload_kind=payload_kind)
        elif isinstance(data, Iterator):
            return IteratorInput(data, payload_kind="token")
        elif isinstance(data, AsyncIterator):
            return AsyncIteratorInput(data, payload_kind="token")
        else:
            raise TypeError(f"Unsupported data type: {type(data)}")
    
    @staticmethod
    def from_path(path: Union[str, Path], 
                  mode: Literal['text', 'binary'] = 'text', 
                  blocksize: int = 4096,
                  encoding: str = "utf-8") -> Input[str] | Input[bytes]:
        path = Path(path)
        if mode == "text":
            f = path.open("r", encoding=encoding)
            return Input.from_stream(f, blocksize=blocksize, mode="text")
        elif mode == "binary":
            fb = path.open("rb")
            return Input.from_stream(fb, blocksize=blocksize, mode="binary")
        else:
            raise ValueError(f"Unknown mode: {mode}")

    @staticmethod
    def from_stream(
        source: Union[io.TextIOBase, io.BufferedIOBase, asyncio.StreamReader],
        blocksize: int = 4096,
        mode: Literal['text', 'binary'] = 'text',
        encoding: str = "utf-8"
    ) -> Input[str] | Input[bytes]:
        if isinstance(source, io.TextIOBase):
            assert mode == 'text', "TextIOBase requires mode='text'"
            def gen_text():
                while True:
                    chunk = source.read(blocksize)
                    if not chunk:
                        break
                    yield chunk
            return IteratorInput(gen_text(), payload_kind="text")

        # Sync binary file
        if isinstance(source, io.BufferedIOBase):
            assert mode == 'binary', "BufferedIOBase requires mode='binary'"
            def gen_binary():
                while True:
                    chunk = source.read(blocksize)
                    if not chunk:
                        break
                    yield chunk
            return IteratorInput(gen_binary(), payload_kind="bytes")

        # Async stream (socket/file-like wrapped by asyncio)
        if isinstance(source, asyncio.StreamReader):
            if mode == 'text':
                return AsyncTextStream(source, encoding=encoding)
            else:
                assert mode == 'binary', "StreamReader requires mode='binary'"
                async def agen_binary():
                    while True:
                        chunk = await source.read(blocksize)
                        if not chunk:
                            break
                        yield chunk
                return AsyncIteratorInput(agen_binary(), payload_kind="bytes")
        raise TypeError(f"Unsupported stream type: {type(source)}")


class StringInput(Input[str]):
    def __init__(self, data: str) -> None:
        super().__init__(payload_kind="text")
        self.data = data
        self.position = 0

    def read(self, n: Optional[int] = None) -> str:
        if self.eof:
            raise EOFError("End of input reached")
        if n is None:
            self.position = len(self.data)
            return self.data
        chunk = self.data[self.position:self.position + n]
        self.position += len(chunk)
        return chunk

    @property
    def eof(self) -> bool:
        return self.position >= len(self.data)
    

class BytesInput(Input[bytes]):
    def __init__(self, data: bytes) -> None:
        super().__init__(payload_kind="bytes")
        self.data = data
        self.position = 0

    def read(self, n: Optional[int] = None) -> bytes:
        if self.eof:
            raise EOFError("End of input reached")
        if n is None:
            self.position = len(self.data)
            return self.data
        chunk = self.data[self.position:self.position + n]
        self.position += len(chunk)
        return chunk

    @property
    def eof(self) -> bool:
        return self.position >= len(self.data)
    

class IteratorInput(Input[T]):
    def __init__(self, data: Iterator[T], *, payload_kind: str = "token") -> None:
        super().__init__(payload_kind=payload_kind)
        self.data = data
        self.done = False

    def read(self, n: Optional[int] = None) -> Sequence[T]:
        if self.eof:
            raise EOFError("End of input reached")
        if n is None:
            self.done = True
            return tuple(self.data)        
        chunk = []
        try:
            for _ in range(n):
                chunk.append(next(self.data))
        except StopIteration:
            self.done = True
        return tuple(chunk)
        
    @property
    def eof(self) -> bool:
        return self.done
    

class AsyncIteratorInput(Input[T]):
    def __init__(self, data: AsyncIterator[T], *, payload_kind: str = "token") -> None:
        super().__init__(payload_kind=payload_kind)
        self.data = data
        self.done = False

    async def aread(self, n: Optional[int] = None) -> Sequence[T]:
        if self.eof:
            raise EOFError("End of input reached")
        if n is None:
            result = []
            async for item in self.data:
                result.append(item)
            self.done = True
            return tuple(result)
        chunk = []
        try:
            for _ in range(n):
                chunk.append(await self.data.__anext__())
        except StopAsyncIteration:
            self.done = True
        return tuple(chunk)

    @property
    def eof(self) -> bool:
        return self.done    
    

class AsyncTextStream(Input[str]):
    def __init__(self, reader: asyncio.StreamReader, encoding="utf-8"):
        super().__init__(payload_kind="text")
        self.reader = reader
        self.decoder = codecs.getincrementaldecoder(encoding)()
        self.buffer = ""

    async def aread(self, n: Optional[int] = None) -> str:
        if self.eof:
            raise EOFError("End of input reached")
        if n is None:
            # read all
            chunks = [self.buffer]
            self.buffer = ""
            while not self.reader.at_eof():
                chunk = await self.reader.read(4096)
                if not chunk:
                    break
                chunks.append(self.decoder.decode(chunk))
            chunks.append(self.decoder.decode(b"", final=True))
            return "".join(chunks)
        else:
            while len(self.buffer) < n:
                chunk = await self.reader.read(n)
                if not chunk:
                    # flush remaining
                    self.buffer += self.decoder.decode(b"", final=True)
                    break
                self.buffer += self.decoder.decode(chunk)
            result, self.buffer = self.buffer[:n], self.buffer[n:]
            return result

    @property
    def eof(self) -> bool:
        return self.reader.at_eof() and not self.buffer





class StreamCursor(Generic[T]):
    """Iterates over an ``Input`` in normalized, non-empty chunks.

    Guarantees that every chunk yielded before EOF has content and that
    callers receive consistent container types (str, bytes, or tuple[T,...]).
    """

    def __init__(self, source: Input[T], *, chunk_size: Optional[int] = None) -> None:
        self.source = source
        self.chunk_size = chunk_size
        if isinstance(source, StringInput):
            self._empty: str | bytes | Tuple[T, ...] = ""
        elif isinstance(source, BytesInput):
            self._empty = b""
        else:
            self._empty = tuple()

    def initial_buffer(self) -> tuple[str | bytes | Tuple[T, ...], bool]:
        if self.source.eof:
            return self._empty, True
        chunk = self._read()
        normalized = self._normalize(chunk)
        return normalized, self.source.eof

    def next_chunk(self) -> tuple[str | bytes | Tuple[T, ...], bool]:
        chunk = self._read()
        normalized = self._normalize(chunk)
        return normalized, self.source.eof

    def empty_like(self) -> str | bytes | Tuple[T, ...]:
        return self._empty

    def _read(self) -> Sequence[T] | str | bytes:
        try:
            if self.chunk_size is None:
                return self.source.read()
            return self.source.read(self.chunk_size)
        except EOFError:
            return self._empty

    def _normalize(self, chunk: Sequence[T] | str | bytes) -> str | bytes | Tuple[T, ...]:
        if isinstance(chunk, str):
            if not chunk and not self.source.eof:
                raise SyncraftError(
                    "Input provided an empty chunk before EOF; unable to progress",
                    offender=self.source,
                    expect="non-empty chunk",
                )
            self._empty = ""
            self.source.mark_payload_kind("text")
            return chunk
        if isinstance(chunk, bytes):
            if not chunk and not self.source.eof:
                raise SyncraftError(
                    "Input provided an empty chunk before EOF; unable to progress",
                    offender=self.source,
                    expect="non-empty chunk",
                )
            self._empty = b""
            self.source.mark_payload_kind("bytes")
            return chunk
        seq = tuple(cast(Sequence[T], chunk))
        if not seq and not self.source.eof:
            raise SyncraftError(
                "Input provided an empty chunk before EOF; unable to progress",
                offender=self.source,
                expect="non-empty chunk",
            )
        self._empty = tuple()
        if seq:
            self.source.mark_payload_kind("token")
        return cast(Tuple[T, ...], seq)
