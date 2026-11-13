"""read(product_text): ask the configured reader, fall back to the fake reader on any error.

The reading is only shown next to the product. Nothing in matching, trust or policy imports this
module, so a reader can never change a decision. A fallback writes one note into the Open Ledger."""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from validio.config import DEFAULT_ENV, _read_env_file
from validio.reader.fake import FakeReader
from validio.reader.schema import ReaderResult


class Reader(Protocol):
    name: str

    def read(self, text: str) -> Any: ...


@dataclass(frozen=True)
class Reading:
    result: ReaderResult
    reader: str  # which reader answered: fake or modal
    fell_back: bool = False
    note: str | None = None


def reader_from_env(env_file: Path | None = DEFAULT_ENV) -> Reader:
    env = _read_env_file(env_file) if env_file else {}
    env.update(os.environ)
    if env.get("READER_MODE", "fake") == "modal":
        from validio.reader.remote import ModalReader

        return ModalReader(env.get("MODAL_GEMMA_URL", ""), env.get("MODAL_GEMMA_TOKEN", ""))
    return FakeReader()


def read(
    product_text: str,
    *,
    reader: Reader | None = None,
    ledger: Any = None,
    now: datetime | None = None,
    product_id: str | None = None,
    env_file: Path | None = DEFAULT_ENV,
) -> Reading:
    reader = reader or reader_from_env(env_file)
    fake = FakeReader()
    if reader.name == fake.name:
        return Reading(fake.read(product_text), fake.name)
    try:
        raw = reader.read(product_text)
        result = raw if isinstance(raw, ReaderResult) else ReaderResult.model_validate(raw)
        return Reading(result, reader.name)
    except Exception as e:  # noqa: BLE001 any failure, even a bad answer, means the fake reader answers
        note = f"The {reader.name} reader failed ({type(e).__name__}), the fake reader answered instead."
        if ledger is not None:
            ledger.append(
                at=now or datetime.now().astimezone(),
                actor="validio",
                kind="reader_fallback",
                sentence=note,
                facts=[{"field": "product", "value": product_id}] if product_id else [],
                mandate_id=None,
                disclosed={},
                rule_ids=[],
                order_id=None,
            )
        return Reading(fake.read(product_text), fake.name, fell_back=True, note=note)
