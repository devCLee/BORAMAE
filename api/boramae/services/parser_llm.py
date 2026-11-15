"""Registration point of the model parser. W5-PARSE-LLM fills it in."""

from collections.abc import Callable

from boramae.config import Settings

# parse(text, lang, catalog, session_id) -> proposal. It raises on a timeout, a
# client error or a refused budget, and the parse router then runs the rules.
ModelParser = Callable[..., object]


def make_model_parser(settings: Settings) -> ModelParser | None:
    """None until the model parser is built, and always None with the LLM off."""
    return None
