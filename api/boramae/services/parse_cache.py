"""The parse cache: validated model proposals by a hash of the question (TDD Flow A).

The key is the SHA-256 of the normalized text, the language, the catalog version and
the prompt version, so neither the path nor the body holds the text. Only a model
proposal that passed the catalog check is put. A rules proposal is never stored, or
a text parsed during one model timeout would get the rules answer for good.
"""

import hashlib
import json

from boramae.contracts.spec import Lang, ParseProposal
from boramae.ports import ObjectStore
from boramae.services.parser_rules import normalize

# Version of the model parser prompt. W5-PARSE-LLM raises it with each prompt change,
# so an entry of an older prompt never answers.
PROMPT_VERSION = "2"
MODEL_SOURCE = "model"


def parse_key(text: str, lang: Lang, catalog_version: str) -> str:
    material = [normalize(text), lang, catalog_version, PROMPT_VERSION]
    encoded = json.dumps(material, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def get_proposal(store: ObjectStore, key: str) -> ParseProposal | None:
    body = store.get(_path(key))
    return None if body is None else ParseProposal.model_validate_json(body)


def put_proposal(store: ObjectStore, key: str, proposal: ParseProposal) -> None:
    """Store a validated model proposal once. An entry never changes."""
    if proposal.source != MODEL_SOURCE:
        raise ValueError("only a validated model proposal enters the parse cache")
    store.create_once(_path(key), proposal.to_json_bytes())


def _path(key: str) -> str:
    return f"parse/{key}.json"
