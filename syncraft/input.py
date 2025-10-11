from __future__ import annotations
from typing import Generic, Iterator, Optional, TypeVar, Sequence, AsyncIterator, Union, Literal, cast
import io
import asyncio
import codecs
from pathlib import Path



T = TypeVar("T")
Chunk = Union[Sequence[T], str, bytes]
class Input(Generic[T]):
    def read(self, n: Optional[int] = None) -> Chunk:
        raise NotImplementedError
    
    async def aread(self, n: Optional[int] = None) -> Chunk:
        return self.read(n)
    
    @property
    def eof(self) -> bool:
        raise NotImplementedError
    
    @staticmethod
    def from_data(data: Union[str, bytes, Iterator[T], AsyncIterator[T], Sequence[T]]) -> Input[str] | Input[bytes] | Input[T]:
        if isinstance(data, str):
            return StringInput(data)
        elif isinstance(data, bytes):
            return BytesInput(data)
        elif isinstance(data, Sequence):
            return IteratorInput(cast(Iterator[T], iter(data)))
        elif isinstance(data, Iterator):
            return IteratorInput(data)
        elif isinstance(data, AsyncIterator):
            return AsyncIteratorInput(data)
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
            return IteratorInput(gen_text())

        # Sync binary file
        if isinstance(source, io.BufferedIOBase):
            assert mode == 'binary', "BufferedIOBase requires mode='binary'"
            def gen_binary():
                while True:
                    chunk = source.read(blocksize)
                    if not chunk:
                        break
                    yield chunk
            return IteratorInput(gen_binary())

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
                return AsyncIteratorInput(agen_binary())
        raise TypeError(f"Unsupported stream type: {type(source)}")


class StringInput(Input[str]):
    def __init__(self, data: str) -> None:
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
    def __init__(self, data: Iterator[T]) -> None:
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
    def __init__(self, data: AsyncIterator[T]) -> None:
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
