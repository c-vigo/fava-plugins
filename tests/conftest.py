from __future__ import annotations

import pytest
from beancount.core import data
from beancount.loader import load_string
from beancount.loader import OptionsMap

LoaderResult = tuple[data.Directives, list[data.BeancountError], OptionsMap]


@pytest.fixture
def load_doc(
    request: pytest.FixtureRequest,
) -> LoaderResult:
    return load_string(request.function.__doc__, dedent=True)
