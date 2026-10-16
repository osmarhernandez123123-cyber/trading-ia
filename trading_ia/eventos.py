"""Contrato futuro de información puntual; no contiene decisiones de trading."""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, Sequence
import re


@dataclass(frozen=True)
class Evento:
    id: str
    tipo: Literal['noticia', 'macro', 'empresa']
    fuente: str
    publicado: datetime
    recibido: datetime
    disponible: datetime
    contenido_sha256: str
    revision: int = 1

    def __post_init__(self):
        tiempos = (self.publicado, self.recibido, self.disponible)
        if any(t.tzinfo is None or t.utcoffset() is None for t in tiempos):
            raise ValueError('Timestamps con zona horaria verificable obligatorios')
        if not self.publicado <= self.recibido <= self.disponible:
            raise ValueError('Orden temporal inválido')
        if not self.id or not self.fuente or self.revision < 1:
            raise ValueError('Identidad, fuente y revisión obligatorias')
        if self.tipo not in {'noticia', 'macro', 'empresa'} or not re.fullmatch('[0-9a-f]{64}', self.contenido_sha256):
            raise ValueError('Tipo o SHA-256 inválido')

    def visible(self, instante: datetime) -> bool:
        if instante.tzinfo is None:
            raise ValueError('Consulta sin zona horaria')
        return self.disponible <= instante


class FuenteEventos(Protocol):
    def consultar(self, hasta: datetime) -> Sequence[Evento]:
        """Solo revisiones disponibles en `hasta`; conservar histórico de revisiones."""
        ...
