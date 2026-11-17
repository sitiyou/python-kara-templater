"""Narrow typed boundary around the optional ModernGL dependency."""

from typing import Protocol


class Resource(Protocol):
    def release(self) -> None: ...


class Uniform(Protocol):
    value: object

    def write(self, data: bytes) -> None: ...


class Program(Resource, Protocol):
    def __getitem__(self, name: str) -> Uniform: ...


class Texture(Resource, Protocol):
    filter: tuple[int, int]
    repeat_x: bool
    repeat_y: bool

    def use(self, location: int = 0) -> None: ...


class VertexArray(Resource, Protocol):
    def render(self, mode: int) -> None: ...


class Framebuffer(Resource, Protocol):
    def use(self) -> None: ...
    def clear(self, red: float, green: float, blue: float, alpha: float) -> None: ...
    def read(self, *, components: int, alignment: int) -> bytes: ...


class Context(Resource, Protocol):
    info: dict[str, object]
    blend_func: tuple[int, int]

    def enable(self, flags: int) -> None: ...
    def program(self, *, vertex_shader: str, fragment_shader: str) -> Program: ...
    def buffer(self, data: bytes) -> Resource: ...
    def texture(
        self, size: tuple[int, int], components: int, data: bytes, *, alignment: int
    ) -> Texture: ...
    def vertex_array(
        self, program: Program, content: list[tuple[Resource, str, str]]
    ) -> VertexArray: ...
    def simple_framebuffer(
        self, size: tuple[int, int], *, components: int
    ) -> Framebuffer: ...


class Driver(Protocol):
    BLEND: int
    ONE: int
    ONE_MINUS_SRC_ALPHA: int
    LINEAR: int
    TRIANGLE_STRIP: int

    def create_standalone_context(self, *, require: int, backend: str) -> Context: ...
