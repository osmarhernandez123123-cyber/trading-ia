"""Contratos futuros point-in-time; no generan señales ni decisiones."""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, Iterable


@dataclass(frozen=True)
class Evento:
    identificador: str
    tipo: Literal['noticia', 'macro', 'empresa']
    fuente: str
    contenido_sha256: str
    ocurrido_en: datetime
    publicado_en: datetime
    recibido_en: datetime
    revision: str
    simbolos: tuple[str, ...] = ()

    def __post_init__(self):
        for valor in (self.ocurrido_en, self.publicado_en, self.recibido_en):
            if valor.tzinfo is None or valor.utcoffset() is None:
                raise ValueError('Timestamp debe incluir zona horaria')
        if self.recibido_en < self.publicado_en:
            raise ValueError('Recepción anterior a publicación')
        if len(self.contenido_sha256) != 64 or any(c not in '0123456789abcdef' for c in self.contenido_sha256):
            raise ValueError('SHA-256 inválido')
        if not all((self.identificador, self.fuente, self.revision)) or self.tipo not in ('noticia', 'macro', 'empresa'):
            raise ValueError('Metadatos inválidos')

    def disponible(self, instante: datetime) -> bool:
        if instante.tzinfo is None or instante.utcoffset() is None:
            raise ValueError('Instante sin zona horaria')
        return max(self.publicado_en, self.recibido_en) <= instante


class FuenteEventos(Protocol):
    def disponibles(self, hasta: datetime) -> Iterable[Evento]:
        """Solo revisiones recibidas y publicadas hasta el corte; conservar originales."""
        ...
